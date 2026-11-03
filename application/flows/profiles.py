# ===============================================
#  PROFILE RUNNER
#  Runs one message through the flow of one profile. The profile says which flow, which models (its ModelResolver) and which
#  MCP servers; the service does not choose between flows any more: the client asks a profile and chains them itself
#  (PR-005 section 2). A run that stopped to ask the user is resumed by the next message of the same profile.
#
#  Until flows are files (T-05.12) a profile names a Python flow of flows/registry.py; and until the API carries the profile
#  (T-05.9) the service runs `default` for every message.
# ===============================================

from typing import Iterable, List, Optional

from application.engine.assemble import Agent, AssembledProfile
from application.engine.flow import Flow
from application.engine.pipeline import Pipeline
from application.engine.state.flow_state import FlowState
from application.engine.state.motion_state import MotionFlowState
from application.engine.state.paused_run import FlowResult, PausedRun
from application.engine.support.metrics import SessionMetrics
from application.flows.registry import FLOWS
from application.outbound.ports.llm_ports import LLMOutboundPort
from application.outbound.ports.mcp_ports import McpToolsPort
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
        self.flows = {flow.name: flow for flow in (flows if flows is not None else FLOWS)}

    def run(
        self,
        profile_name: str,
        message: str,
        history: Optional[List[Message]] = None,
        paused: Optional[PausedRun] = None,
        state: Optional[FlowState] = None,
        speak_movements: bool = True,
    ) -> FlowResult:
        """
        The result of the last step of the profile's flow (`result.flow` says which flow ran). `state` is a state made by the
        caller (what a client sends as `inputs`: T-05.9); without it the flow starts a fresh one. `speak_movements` is Brain's
        setting: whether a movement that goes ahead is announced.
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
            if isinstance(state, MotionFlowState):
                state.speak_movements = speak_movements

        pipeline = Pipeline(self.outbound_port, self._servers(profile), self.metrics, self.mcp_tools, flow=flow, models=profile.resolver)
        return pipeline.run(message, list(history or []), paused, state=state)

    # -----------------------------------------------

    def _flow_of(self, profile: AssembledProfile) -> Flow:
        if profile.flow_name is None:
            raise ValueError(f"profile {profile.name!r} lists its own steps: that needs steps as files (T-05.16)")
        if profile.flow_name not in self.flows:
            raise ValueError(f"profile {profile.name!r}: unknown flow {profile.flow_name!r}. Flows: {', '.join(self.flows)}")
        return self.flows[profile.flow_name]

    @staticmethod
    def _servers_named(definition: dict) -> Optional[List[str]]:
        tools = definition.get("tools")
        return None if tools is None else list(tools.get("servers") or [])

    def _servers(self, profile: AssembledProfile) -> list:
        """
        The MCP servers the profile may use: those it names in `tools.servers` (an empty list is none), every configured server
        when it names none (nothing set, no limit). The real scoping (profile, flow and step, and single tools) is T-05.13.
        """
        names = self._servers_named(profile.definition)
        return list(self.mcp_list) if names is None else [server for server in self.mcp_list if server["name"] in names]
