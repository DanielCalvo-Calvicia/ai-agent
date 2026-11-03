"""
A model of the CLIENT's chain, run in-process (PR-005 section 2). The service no longer routes: Brain asks the `identification`
profile, reads the domain and asks the profile that answers (`chat`, `movement`, `special`), then, for a reply, the `gesture`
profile. Many tests were written against that behaviour when the service did it (the old AgentRouter), so this file keeps it, on
top of the real ProfileRunner and the real profiles of profiles/, with the models of the code (what the tests expect).

    AgentRouter                   the old router's logic, as the client's chain
    ChainedMessageFlowService     a MessageFlowService that runs the chain instead of one profile
    ChainedSessionService         a SessionService that builds ChainedMessageFlowService (and takes `models=`)

The production service runs ONE profile per message (tests/test_profiles.py).
"""
import dataclasses
import os
import sys
from functools import partial
from typing import Dict, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.engine.assemble import Agent, assemble
from application.engine.config_snapshot import build_snapshot
from application.engine.flow import Flow
from application.engine.state.expression_state import ExpressionFlowState
from application.engine.state.flow_state import FlowState
from application.engine.state.motion_state import MotionFlowState
from application.engine.state.paused_run import FlowResult, PausedRun
from application.engine.support.expression_settings import speech_seconds
from application.engine.support.metrics import SessionMetrics
from application.engine.support.model_selection import ModelResolver
from application.flows.conversation import CONVERSATION_FLOW
from application.flows.expression import EXPRESSION_FLOW
from application.flows.identification import IDENTIFICATION_FLOW
from application.flows.movement import MOVEMENT_FLOW
from application.flows.profiles import ProfileRunner
from application.flows.registry import FLOWS
from application.flows.special import SPECIAL_FLOW
from application.outbound.ports.llm_ports import LLMOutboundPort
from application.outbound.ports.mcp_ports import McpToolsPort
from application.service.message_flow_service import MessageFlowService
from application.service.session_service import SessionService
from domain.value_objects.llm_request.message import Message
from infrastructure.outbound.config.file_source import FileConfigSource
from shared_logging import get_logger

logger = get_logger(__name__)

# task_category.domain -> the flow that answers. A domain that is not listed goes to the special flow.
FLOW_BY_DOMAIN: Dict[str, Flow] = {
    "communication": CONVERSATION_FLOW,
    "movement": MOVEMENT_FLOW,
}
DEFAULT_FLOW = SPECIAL_FLOW

# The flows whose reply gets a gesture. The movement flow's does not: the user asked for movements, the robot does those.
EXPRESSIVE_FLOWS = (CONVERSATION_FLOW.name, SPECIAL_FLOW.name)

PROFILE_OF_FLOW = {
    IDENTIFICATION_FLOW.name: "identification",
    CONVERSATION_FLOW.name: "chat",
    SPECIAL_FLOW.name: "special",
    MOVEMENT_FLOW.name: "movement",
    EXPRESSION_FLOW.name: "gesture",
}

# The client has just asked `identification`: it asks `special` WITHOUT the triage that profile starts with, so nothing is
# classified twice (a client that asks both pays for two triages, and the service says nothing: PR-005 section 3.3).
SPECIAL_AFTER_TRIAGE = dataclasses.replace(SPECIAL_FLOW, build_steps=lambda context: SPECIAL_FLOW.build_steps(context)[1:])


def expression_enabled() -> bool:
    """The knob of the tests for the gesture the chain asks after a reply (the service has none: the client asks `gesture`)."""
    return os.environ.get("AI_AGENT_EXPRESSION", "1").strip().lower() not in ("0", "false", "no", "off")


def test_agent(models: Optional[ModelResolver] = None) -> Agent:
    """The real profiles of profiles/, every one with `models` (none: the default model of each step), as the tests expect."""
    agent = assemble(build_snapshot(FileConfigSource(PROJECT_ROOT)), known_flows={flow.name for flow in FLOWS})
    agent.raise_on_errors()
    profiles = {name: dataclasses.replace(profile, resolver=models or ModelResolver()) for name, profile in agent.profiles.items()}
    return Agent(profiles, agent.problems)


def flow_for(state: FlowState) -> Flow:
    """The flow that answers a message, from the domain the identification flow found."""
    domain = state.task_category.domain.get_value() if state.task_category and state.task_category.domain else None
    return FLOW_BY_DOMAIN.get(domain or "", DEFAULT_FLOW)


class AgentRouter:
    """The old router's logic as the client's chain: identification, then the profile of the domain, then a gesture."""

    def __init__(
        self,
        outbound_port: LLMOutboundPort,
        mcp_list: list,
        metrics: SessionMetrics,
        mcp_tools: Optional[McpToolsPort] = None,
        models: Optional[ModelResolver] = None,
    ) -> None:
        flows = [flow for flow in FLOWS if flow.name != SPECIAL_FLOW.name] + [SPECIAL_AFTER_TRIAGE]
        self.runner = ProfileRunner(outbound_port, mcp_list, metrics, mcp_tools, test_agent(models), flows=flows)

    def run(
        self,
        message: str,
        history: Optional[List[Message]] = None,
        paused: Optional[PausedRun] = None,
        speak_movements: bool = True,
    ) -> FlowResult:
        result = self._run(message, history, paused, speak_movements)
        return self._with_gesture(message, result)

    def _run(self, message, history, paused, speak_movements) -> FlowResult:
        history = list(history or [])

        if paused is not None:
            result = self.runner.run(PROFILE_OF_FLOW[paused.flow], message, history, paused, speak_movements=speak_movements)
            if paused.flow != IDENTIFICATION_FLOW.name or result.paused or result.ended_early or result.state is None:
                return result
            return self._answer(result.state, history, speak_movements)

        result = self.runner.run("identification", message, history)
        if result.paused or result.state is None:
            return result                                            # triage needs a detail first
        return self._answer(result.state, history, speak_movements)

    def _answer(self, identified: FlowState, history: List[Message], speak_movements: bool) -> FlowResult:
        flow = flow_for(identified)
        state = flow.new_state(identified.message, history)
        state.take_over(identified)
        if isinstance(state, MotionFlowState):
            state.speak_movements = speak_movements
        return self.runner.run(PROFILE_OF_FLOW[flow.name], identified.message, history, state=state, speak_movements=speak_movements)

    def _with_gesture(self, message: str, result: FlowResult) -> FlowResult:
        if (not expression_enabled() or result.flow not in EXPRESSIVE_FLOWS or result.ended_early
                or result.movements or not result.reply.strip()):
            return result

        try:
            state = ExpressionFlowState(message=message, reply=result.reply, speech_seconds=speech_seconds(result.reply))
            gesture = self.runner.run("gesture", message, [], state=state)
        except Exception as error:
            logger.warning("No gesture for this reply: the expression flow failed", error_type=type(error).__name__)
            return result

        if gesture.movements:
            result.movements = gesture.movements
            result.gesture = True
        return result


class ChainedMessageFlowService(MessageFlowService):
    """A MessageFlowService that runs the client's chain (AgentRouter) instead of the one profile the service runs."""

    def __init__(self, outbound_port, mcp_list=None, history=None, mcp_tools=None, paused=None, usage_reporter=None,
                 models: Optional[ModelResolver] = None, **ignored) -> None:
        super().__init__(outbound_port, mcp_list, history, mcp_tools, paused, usage_reporter)
        self.router = AgentRouter(outbound_port, self.mcp_list, self.metrics, mcp_tools, models)

    def main_flow(self, message: str, speak_movements: bool = True):
        result = self.router.run(message, self.history, self.paused, speak_movements)
        self.paused_run = result.paused
        return result


class ChainedSessionService(SessionService):
    """A SessionService whose messages run the client's chain; it takes `models=` like the service did before profiles."""

    def __init__(self, outbound_port, message_service_type=ChainedMessageFlowService, mcp_list=None, history_turns: int = 6,
                 mcp_tools=None, usage_reporter=None, models: Optional[ModelResolver] = None, **kwargs) -> None:
        if models is not None:
            message_service_type = partial(message_service_type, models=models)
        super().__init__(outbound_port, message_service_type, mcp_list, history_turns, mcp_tools, usage_reporter, **kwargs)
