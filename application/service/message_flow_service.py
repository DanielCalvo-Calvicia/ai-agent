# ===============================================
#  MESSAGE FLOW SERVICE
#  Inbound adapter for one user message. The phases live in
#  application/orchestration; see Pipeline for the order.
# ===============================================

from typing import List, Optional

from application.inbound.dto.message import TextRequestDTO, TextResponseDTO
from application.inbound.ports.message_flow_ports import MessageInboundPort
from application.orchestration.engine.flow import Flow
from application.orchestration.flows.conversation_flow import CONVERSATION_FLOW
from application.orchestration.support.metrics import SessionMetrics
from application.orchestration.state.paused_run import PausedRun
from application.orchestration.engine.pipeline import Pipeline
from application.outbound.ports.llm_ports import LLMOutboundPort
from application.outbound.ports.mcp_ports import McpToolsPort
from application.outbound.ports.usage_ports import UsageReporterPort
from domain.value_objects.message import Message
from domain.value_objects.motion.robot_context import RobotContext


class MessageFlowService(MessageInboundPort):
    outbound_port: LLMOutboundPort
    mcp_list: list
    metrics: SessionMetrics
    pipeline: Pipeline

    def __init__(
        self,
        outbound_port: LLMOutboundPort,
        mcp_list: Optional[list] = None,
        history: Optional[List[Message]] = None,
        mcp_tools: Optional[McpToolsPort] = None,
        paused: Optional[PausedRun] = None,
        usage_reporter: Optional[UsageReporterPort] = None,
        flow: Flow = CONVERSATION_FLOW,
    ):
        self.outbound_port = outbound_port
        self.history = list(history or [])
        self.paused = paused
        self.paused_run: Optional[PausedRun] = paused   # after text(): the run still waiting for the user, if any
        self.metrics = SessionMetrics(usage_reporter)
        self.mcp_list = mcp_list if mcp_list is not None else []
        self.pipeline = Pipeline(outbound_port, self.mcp_list, self.metrics, mcp_tools, flow=flow)

    def text(self, request: TextRequestDTO) -> TextResponseDTO:
        self.metrics.begin_message(request.request_id, request.session_name or request.session_id, request.content)
        robot_context = request.robot_context.to_domain() if request.robot_context else None
        result = self.main_flow(request.content, robot_context)
        return TextResponseDTO(
            content=result.reply,
            movements=list(result.movements),
            awaiting_user_input=result.paused is not None,
            is_final=True,
            success=True
        )

    def main_flow(self, message: str, robot_context: Optional[RobotContext] = None):
        result = self.pipeline.run(message, self.history, self.paused, robot_context)
        self.paused_run = result.paused
        return result
