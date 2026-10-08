# ===============================================
#  MESSAGE FLOW SERVICE
#  Inbound adapter for one user message. The flows live in
#  application/orchestration; the router (flows/router.py) says which one answers.
# ===============================================

from typing import List, Optional

from application.inbound.dto.message import TextRequestDTO, TextResponseDTO
from application.inbound.ports.message_flow_ports import MessageInboundPort
from application.orchestration.flows.router import AgentRouter
from application.orchestration.support.metrics import SessionMetrics
from application.orchestration.state.paused_run import PausedRun
from application.outbound.ports.llm_ports import LLMOutboundPort
from application.outbound.ports.mcp_ports import McpToolsPort
from application.outbound.ports.usage_ports import UsageReporterPort
from domain.value_objects.llm_request.message import Message


class MessageFlowService(MessageInboundPort):
    outbound_port: LLMOutboundPort
    mcp_list: list
    metrics: SessionMetrics
    router: AgentRouter

    def __init__(
        self,
        outbound_port: LLMOutboundPort,
        mcp_list: Optional[list] = None,
        history: Optional[List[Message]] = None,
        mcp_tools: Optional[McpToolsPort] = None,
        paused: Optional[PausedRun] = None,
        usage_reporter: Optional[UsageReporterPort] = None,
    ):
        self.outbound_port = outbound_port
        self.history = list(history or [])
        self.paused = paused
        self.paused_run: Optional[PausedRun] = paused   # after text(): the run still waiting for the user, if any
        self.metrics = SessionMetrics(usage_reporter)
        self.mcp_list = mcp_list if mcp_list is not None else []
        self.router = AgentRouter(outbound_port, self.mcp_list, self.metrics, mcp_tools)

    def text(self, request: TextRequestDTO) -> TextResponseDTO:
        self.metrics.begin_message(str(request.request_id), request.session_name or request.session_id, request.content)
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
        result = self.router.run(message, self.history, self.paused, speak_movements)
        self.paused_run = result.paused
        return result
