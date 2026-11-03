# ===============================================
#  PROFILE RUNNER
#  Runs one message through the flow of one profile. The profile says which flow, which models (its ModelResolver) and which
#  tools (the limits of the profile, the flow and the step, T-05.13); the service does not choose between flows any more: the client asks a profile and chains them itself
#  (PR-005 section 2). A run that stopped to ask the user is resumed by the next message of the same profile.
#
#  A profile names a flow file (flows/<name>.json); the Agent holds the Flow built from each one (assemble.py).
# ===============================================

from typing import Iterable, List, Optional

from application.engine.assemble import Agent, AssembledProfile
from application.engine.flow import Flow
from application.engine.pipeline import Pipeline
from application.engine.state.expression_state import ExpressionFlowState
from application.engine.state.flow_state import FlowState
from application.engine.state.motion_state import MotionFlowState
from application.engine.state.paused_run import FlowResult, PausedRun
from application.engine.support.expression_settings import speech_seconds
from application.engine.support.metrics import SessionMetrics
from application.outbound.ports.llm_ports import LLMOutboundPort
from application.outbound.ports.mcp_ports import McpToolsPort, scoped
from domain.value_objects.llm_request.message import Message


class ProfileMismatch(ValueError):
    """The run waiting for the user belongs to another profile (T-05.9 turns it into PROFILE_MISMATCH)."""


class ProfileRunner:
    def __init__(
        self,
        outbound_port: LLMOutboundPort,
        mcp_list: list,
        metrics: SessionMetrics,
        mcp_tools: Optional[McpToolsPort] = None,
        agent: Optional[Agent] = None,
        flows: Optional[Iterable[Flow]] = None,
    ) -> None:
        self.outbound_port = outbound_port
        self.mcp_list = mcp_list
        self.metrics = metrics
        self.mcp_tools = mcp_tools
        self.agent = agent
        self.flows = {flow.name: flow for flow in (flows if flows is not None else (agent.flows.values() if agent else []))}

    def run(
        self,
        profile_name: str,
        message: str,
        history: Optional[List[Message]] = None,
        paused: Optional[PausedRun] = None,
        state: Optional[FlowState] = None,
        speak_movements: bool = True,
        inputs: Optional[dict] = None,
    ) -> FlowResult:
        """
        The result of the last step of the profile's flow (`result.flow` says which flow ran). `state` is a state made by the
        caller (what a client sends as `inputs`: T-05.9); without it the flow starts a fresh one. `speak_movements` is Brain's
        setting: whether a movement that goes ahead is announced. `inputs` are the values of state fields the client sent (read already);
        a gesture gets the length of its speech from the reply when none was sent.
        """
        if self.agent is None:
            raise ValueError("the service has no agent: the profiles were not assembled")
        profile = self.agent.profile(profile_name)                 # KeyError: unknown or disabled
        flow = self._flow_of(profile)

        if paused is not None:
            if paused.flow != flow.name:
                raise ProfileMismatch(f"the run waiting for the user belongs to the flow {paused.flow!r}, not to profile {profile_name!r}")
            if isinstance(paused.state, MotionFlowState):
                paused.state.speak_movements = speak_movements     # Brain's setting of this message, not of the one that paused
        else:
            state = state if state is not None else flow.new_state(message, list(history or []))
            self._apply_inputs(state, inputs)
            if isinstance(state, MotionFlowState):
                state.speak_movements = speak_movements

        pipeline = self._pipeline(profile, flow)
        return pipeline.run(message, list(history or []), paused, state=state)

    # -----------------------------------------------

    def _pipeline(self, profile: AssembledProfile, flow: Flow) -> Pipeline:
        definition = profile.definition
        return Pipeline(self.outbound_port, self.mcp_list, self.metrics, self.mcp_tools, flow=flow, models=profile.resolver,
                        tool_levels=(definition.get("tools"), ((definition.get("flows") or {}).get(flow.name) or {}).get("tools")),
                        tool_overrides={step: entry["tools"] for step, entry in (definition.get("overrides") or {}).items()
                                        if isinstance(entry, dict) and isinstance(entry.get("tools"), dict)})

    def servers_of(self, profile_name: str, step: Optional[str] = None) -> List[str]:
        """The MCP servers the profile (or one of its steps) may use: those with a tool every level of the scope allows."""
        profile = self.agent.profile(profile_name)
        scope = self._pipeline(profile, self._flow_of(profile)).scope_of(step)
        return [server["name"] for server in scoped(self.mcp_list, self.mcp_tools, scope)[0]]

    @staticmethod
    def _apply_inputs(state: FlowState, inputs: Optional[dict]) -> None:
        for name, value in (inputs or {}).items():
            setattr(state, name, value)
        if isinstance(state, ExpressionFlowState) and inputs and "reply" in inputs and "speech_seconds" not in inputs:
            state.speech_seconds = speech_seconds(state.reply)

    def _flow_of(self, profile: AssembledProfile) -> Flow:
        if profile.flow_name is None:
            raise ValueError(f"profile {profile.name!r} lists its own steps: that needs steps as files (T-05.16)")
        if profile.flow_name not in self.flows:
            raise ValueError(f"profile {profile.name!r}: unknown flow {profile.flow_name!r}. Flows: {', '.join(self.flows)}")
        return self.flows[profile.flow_name]
