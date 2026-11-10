# ===============================================
#  MESSAGE FLOW SERVICE
#  Inbound adapter for one user message. The profile asked runs its flow (flows/<name>.json, built by assemble).
# ===============================================

from typing import List, Optional

from application.inbound.dto.message import TextRequestDTO, TextResponseDTO
from application.inbound.ports.message_flow_ports import MessageInboundPort
from application.assembly.model import DEFAULT_PROFILE, Agent
from application.runtime.state.history import response_of
from application.runtime.profile.runner import ProfileRunner
from application.support.metrics import SessionMetrics
from application.runtime.state.paused_run import PausedRun
from application.outbound.ports.llm_ports import LLMOutboundPort
from application.outbound.ports.mcp_ports import McpToolsPort
from application.outbound.ports.usage_ports import UsageReporterPort
from domain.entities.llm_response.response import Response
from domain.value_objects.llm_request.message import Message


class MessageFlowService(MessageInboundPort):
    outbound_port: LLMOutboundPort
    mcp_list: list
    metrics: SessionMetrics
    runner: ProfileRunner

    def __init__(
        self,
        outbound_port: LLMOutboundPort,
        mcp_list: Optional[list] = None,
        history: Optional[List[Message]] = None,
        mcp_tools: Optional[McpToolsPort] = None,
        paused: Optional[PausedRun] = None,
        usage_reporter: Optional[UsageReporterPort] = None,
        agent: Optional[Agent] = None,
        profile: str = DEFAULT_PROFILE,
        inputs: Optional[dict] = None,
        client: Optional[str] = None,
        cost_of=None,
    ):
        self.outbound_port = outbound_port
        self.history = list(history or [])
        self.paused = paused
        self.paused_run: Optional[PausedRun] = paused   # after text(): the run still waiting for the user, if any
        self.last_response: Optional[Response] = None   # after text(): the Response of the run, None when it had no user_goal
        self.metrics = SessionMetrics(usage_reporter, cost_of=cost_of)
        self.client = client or ""                       # trust-based, for the metrics (Q06-19)
        self.agent = agent
        self.mcp_list = mcp_list if mcp_list is not None else []
        self.inputs = inputs or {}
        self.profile = profile                           # until the API carries it (T-05.9) every message runs `default`
        self.runner = ProfileRunner(outbound_port, self.mcp_list, self.metrics, mcp_tools, agent)

    def text(self, request: TextRequestDTO) -> TextResponseDTO:
        assembled = self.agent.profiles.get(self.profile) if self.agent else None
        self.metrics.begin_message(str(request.request_id), request.session_name or request.session_id, request.content,
                                   profile=self.profile if assembled else "", flow=(assembled.flow_name or "") if assembled else "",
                                   client=self.client, profile_hash=assembled.profile_hash if assembled else "")
        result = self.main_flow(request.content, request.speak_movements)
        return TextResponseDTO(
            content=result.reply,
            movements=list(result.movements),
            gesture=result.gesture,
            awaiting_user_input=result.paused is not None,
            flow=result.flow,
            is_final=True,
            success=True
        )

    def main_flow(self, message: str, speak_movements: bool = True):
        result = self.runner.run(self.profile, message, self.history, self.paused, speak_movements=speak_movements, inputs=self.inputs)
        self.paused_run = result.paused
        self.last_response = response_of(result)
        return result
