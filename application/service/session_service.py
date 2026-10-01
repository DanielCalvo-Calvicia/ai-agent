# ===============================================
#  SESSION SERVICE
#  Starts and ends sessions and hands each message to the agent
#  together with what the session remembers.
# ===============================================

import uuid
from typing import Any, Dict, List, Optional

from application.inbound.dto.message import TextRequestDTO
from application.orchestration.support.failure import UNKNOWN_SESSION_APOLOGY, apology_for_unexpected, classify
from application.inbound.dto.session import (
    EndSessionRequestDTO,
    EndSessionResponseDTO,
    MessageReceivedRequestDTO,
    MessageReceivedResponseDTO,
    StartSessionRequestDTO,
    StartSessionResponseDTO,
)
from application.inbound.ports.message_flow_ports import MessageInboundPort
from application.inbound.ports.session import SessionInboundPort
from application.orchestration.engine.flow import Flow
from application.orchestration.flows.conversation_flow import CONVERSATION_FLOW
from application.outbound.ports.llm_ports import LLMOutboundPort
from application.outbound.ports.mcp_ports import McpToolsPort
from application.outbound.ports.usage_ports import UsageReporterPort
from application.service.message_flow_service import MessageFlowService
from application.service.user_session import UserSession
from shared_logging import current_context, get_logger

logger = get_logger(__name__)


def _current_correlation_id() -> Optional[str]:
    context = current_context()
    return (context.correlation_id or context.trace_id) if context else None


class SessionService(SessionInboundPort):
    def __init__(
        self,
        outbound_port: LLMOutboundPort,
        message_service_type: type[MessageInboundPort] = MessageFlowService,
        mcp_list: Optional[List[Dict[str, Any]]] = None,
        history_turns: int = 6,
        mcp_tools: Optional[McpToolsPort] = None,
        usage_reporter: Optional[UsageReporterPort] = None,
        flow: Flow = CONVERSATION_FLOW,
    ) -> None:
        self.flow = flow              # the agent this service's sessions talk to
        self.usage_reporter = usage_reporter
        self.llm_adapter = outbound_port
        self.message_service_type = message_service_type
        self.mcp_list = mcp_list if mcp_list is not None else []
        self.history_turns = history_turns
        self.mcp_tools = mcp_tools
        self.sessions: Dict[str, UserSession] = {}

    def start_session(self, request: StartSessionRequestDTO) -> StartSessionResponseDTO:
        try:
            session_id = str(uuid.uuid4())
            self.sessions[session_id] = UserSession(
                session_id=session_id,
                username=request.username,
                email=request.email,
                name=(request.session_name or "").strip() or None,
            )
            return StartSessionResponseDTO(
                session_id=session_id,
                message="Session started successfully.",
                success=True
            )
        except Exception as e:
            return StartSessionResponseDTO(
                session_id="",
                message=f"Failed to start session: {str(e)}",
                success=False,
                error_code=classify(e).upper(),
            )

    def end_session(self, request: EndSessionRequestDTO) -> EndSessionResponseDTO:
        if self.sessions.pop(request.session_id, None) is None:
            return EndSessionResponseDTO(success=False, message="Session ID not found.",
                                          error_code="SESSION_NOT_FOUND")

        return EndSessionResponseDTO(success=True, message="Session ended successfully.")

    def message_received(self, request: MessageReceivedRequestDTO) -> MessageReceivedResponseDTO:
        user_session = self.sessions.get(request.session_id)
        if user_session is None:
            return self._failed("Session ID not found.", UNKNOWN_SESSION_APOLOGY, "SESSION_NOT_FOUND")

        try:
            result = self._run_agent(request, user_session)
            user_session.remember(request.message, result.content, self.history_turns)
            return MessageReceivedResponseDTO(response=result.content, movements=list(result.movements),
                                              awaiting_user_input=result.awaiting_user_input, success=True)
        except Exception as e:
            logger.exception("Failed to process message", session_id=request.session_id)
            return self._failed(f"Failed to process message: {str(e)}", apology_for_unexpected(e),
                                 classify(e).upper())

    def _run_agent(self, request: MessageReceivedRequestDTO, user_session: UserSession):
        extra = {"usage_reporter": self.usage_reporter} if self.usage_reporter is not None else {}
        agent: MessageInboundPort = self.message_service_type(
            outbound_port=self.llm_adapter,
            mcp_list=self.mcp_list,
            history=user_session.history,
            mcp_tools=self.mcp_tools,
            paused=user_session.paused,
            flow=self.flow,
            **extra,
        )
        text_request = TextRequestDTO(
            request_id=request.request_id,
            user_id=request.user_id,
            # The DTO field is kept for API compatibility; the active trace is the source of truth.
            correlation_id=request.correlation_id or _current_correlation_id(),
            metadata=request.metadata,
            timestamp=request.timestamp,
            session_id=request.session_id,
            content=request.message,
            session_name=user_session.name,
            robot_context=request.robot_context,
        )
        result = agent.text(text_request)
        user_session.paused = getattr(agent, "paused_run", None)   # only when the message was processed: a failure keeps the old one
        return result

    def is_available(self) -> bool:
        return self.llm_adapter.is_available()

    @staticmethod
    def _failed(reason: str, apology: str, error_code: Optional[str] = None) -> MessageReceivedResponseDTO:
        # `response` is an apology that says what happened and why, so it can be spoken.
        # `message` is the technical reason.
        return MessageReceivedResponseDTO(response=apology, message=reason, success=False, error_code=error_code)
