# ===============================================
#  ROUTER
#  Runs one user message through the agents: the identification flow first (triage), then the one flow that
#  answers, chosen by task_category.domain:
#
#      communication -> conversation   (a plain reply)
#      movement      -> movement       (arm movements)
#      anything else -> special        (plan, check, execute, write)
#
#  The chosen flow starts from the state identification left, so nothing is classified twice. A flow that stopped to
#  ask the user a question is resumed by the next message, without identifying it again: the paused run says which
#  flow it belongs to. The flows never call each other; only the router moves a message from one to the next.
# ===============================================

from typing import Dict, List, Optional

from application.orchestration.engine.flow import Flow
from application.orchestration.engine.pipeline import Pipeline
from application.orchestration.flows.conversation import CONVERSATION_FLOW
from application.orchestration.flows.identification import IDENTIFICATION_FLOW
from application.orchestration.flows.movement import MOVEMENT_FLOW
from application.orchestration.flows.registry import FLOWS
from application.orchestration.flows.special import SPECIAL_FLOW
from application.orchestration.state.flow_state import FlowState
from application.orchestration.state.motion_state import MotionFlowState
from application.orchestration.state.paused_run import FlowResult, PausedRun
from application.orchestration.support.metrics import SessionMetrics
from application.outbound.ports.llm_ports import LLMOutboundPort
from application.outbound.ports.mcp_ports import McpToolsPort
from domain.value_objects.llm_request.message import Message
from shared_logging import get_logger

logger = get_logger(__name__)

# task_category.domain -> the flow that answers. A domain that is not listed goes to SPECIAL_FLOW.
FLOW_BY_DOMAIN: Dict[str, Flow] = {
    "communication": CONVERSATION_FLOW,
    "movement": MOVEMENT_FLOW,
}
DEFAULT_FLOW = SPECIAL_FLOW


def flow_for(state: FlowState) -> Flow:
    """The flow that answers a message, from the domain the identification flow found."""
    domain = state.task_category.domain.get_value() if state.task_category and state.task_category.domain else None
    return FLOW_BY_DOMAIN.get(domain or "", DEFAULT_FLOW)


class AgentRouter:
    def __init__(
        self,
        outbound_port: LLMOutboundPort,
        mcp_list: list,
        metrics: SessionMetrics,
        mcp_tools: Optional[McpToolsPort] = None,
    ) -> None:
        self.pipelines: Dict[str, Pipeline] = {
            flow.name: Pipeline(outbound_port, mcp_list, metrics, mcp_tools, flow=flow) for flow in FLOWS
        }

    def run(
        self,
        message: str,
        history: Optional[List[Message]] = None,
        paused: Optional[PausedRun] = None,
        speak_movements: bool = True,
    ) -> FlowResult:
        """
        The reply, the movements and the run that is still waiting for the user (if any). `result.flow` says which
        flow produced it. `speak_movements` is Brain's setting: whether a movement that goes ahead is announced.
        """
        history = list(history or [])

        if paused is not None:
            if isinstance(paused.state, MotionFlowState):
                paused.state.speak_movements = speak_movements       # Brain's setting of this message, not of the one that paused
            result = self.pipelines[paused.flow].run(message, history, paused)
            if paused.flow != IDENTIFICATION_FLOW.name or result.paused or result.ended_early or result.state is None:
                return result
            return self._answer(result.state, history, speak_movements)

        result = self.pipelines[IDENTIFICATION_FLOW.name].run(message, history)
        if result.paused or result.state is None:
            return result                                            # triage needs a detail first

        return self._answer(result.state, history, speak_movements)

    def _answer(self, identified: FlowState, history: List[Message], speak_movements: bool) -> FlowResult:
        """Hands the identified message to the flow that answers it."""
        flow = flow_for(identified)
        logger.info("Routing message", flow=flow.name,
                    domain=identified.task_category.domain.get_value() if identified.task_category else "")

        state = flow.new_state(identified.message, history)
        state.take_over(identified)
        if isinstance(state, MotionFlowState):
            state.speak_movements = speak_movements

        return self.pipelines[flow.name].run(identified.message, history, state=state)
