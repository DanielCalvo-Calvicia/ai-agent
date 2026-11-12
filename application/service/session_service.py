# ===============================================
#  SESSION SERVICE
#  Starts and ends sessions and hands each message to the agent
#  together with what the session remembers.
# ===============================================

import re
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from application.support.llm.failure import UNKNOWN_SESSION_APOLOGY, apology_for_unexpected, classify
from application.runtime.profile.assembled import DEFAULT_PROFILE, Agent, AssembledProfile
from application.runtime.profile.access import check_access
from application.runtime.profile.inputs import InputsError, read_inputs
from application.runtime.state.response_json import response_to_json
from application.mappers.inbound.message_mapper import message_response_of, text_request_of
from application.dtos.inbound.session import (
    EndSessionRequestDTO,
    EndSessionResponseDTO,
    MessageReceivedRequestDTO,
    MessageReceivedResponseDTO,
    StartSessionRequestDTO,
    StartSessionResponseDTO,
)
from application.ports.inbound.message_flow_ports import MessageInboundPort
from application.ports.inbound.session import SessionInboundPort
from application.ports.outbound.llm_ports import LLMOutboundPort
from application.ports.outbound.mcp_ports import McpToolsPort
from application.ports.outbound.usage_ports import UsageReporterPort
from application.service.message_flow_service import MessageFlowService
from application.service.user_session import UserSession
from domain.entities.llm_response.response import Response
from shared_logging import current_context, get_logger

logger = get_logger(__name__)

# Errors of a request that names a profile (PR-005 section 6). One generic refusal for an unknown profile and a wrong token, so a
# client cannot find out which profiles exist; the real reason is only in the log.
INVALID_PROFILE = "INVALID_PROFILE"
PROFILE_MISMATCH = "PROFILE_MISMATCH"
PAUSE_NOT_FOUND = "PAUSE_NOT_FOUND"
_REFUSALS = {
    INVALID_PROFILE: ("Invalid profile or token.", "Sorry, I cannot use that profile. Please check the profile and its token."),
    PROFILE_MISMATCH: ("The question that is waiting for an answer belongs to another profile.",
                       "Sorry, that answer is for another conversation step. Please answer it with the same profile."),
    PAUSE_NOT_FOUND: ("No question is waiting with that pause_id.",
                      "Sorry, I am not waiting for that answer any more. Please say it again as a new message."),
}
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


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
        agent: Optional[Agent] = None,
        profile: str = DEFAULT_PROFILE,
        response_reader: Optional[Callable[[dict], Response]] = None,
        cost_of=None,
    ) -> None:
        self.response_reader = response_reader     # reads the sections of a Response a client sends in `inputs`
        self.agent = agent
        self.cost_of = cost_of                     # model, tokens -> USD, for the metrics (the prices are in config/)
        self.profile = profile
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
            profile = self._profile(request)
            if profile is None and self.agent is not None:
                return self._refused(INVALID_PROFILE)
            profile_name = profile.name if profile is not None else self.profile

            paused, discarded, refusal = self._question(request, user_session, profile_name)
            if refusal:
                return self._refused(refusal)

            values = {}
            if profile is not None and paused is None:
                try:
                    values = read_inputs(profile, request.inputs, self.response_reader)
                except InputsError as error:
                    return self._failed(str(error), str(error), error.code)

            result, response = self._run_agent(request, user_session, profile_name, paused, values)
            if response is not None:                     # a run with no user_goal (the gesture, a movement nobody classified) adds no entry
                user_session.remember(request.message, result.content, self.history_turns, response)
            user_session.pause_id = uuid.uuid4().hex if user_session.paused is not None else None
            user_session.paused_profile = profile_name if user_session.paused is not None else None

            legacy = request.profile is None and request.pause_id is None      # a request with none of the new fields: today's answer
            mode = request.return_ or (profile.default_return if profile is not None else "text")
            return message_response_of(
                result, request, None if legacy else user_session.pause_id,
                response_to_json(response) if mode == "full" and response is not None else None, discarded)
        except Exception as e:
            logger.exception("Failed to process message", session_id=request.session_id)
            return self._failed(f"Failed to process message: {str(e)}", apology_for_unexpected(e),
                                 classify(e).upper())

    # -----------------------------------------------
    #  WHICH PROFILE, WHICH QUESTION
    # -----------------------------------------------

    def _profile(self, request: MessageReceivedRequestDTO) -> Optional[AssembledProfile]:
        """The profile the request may run, or None. A request that names none runs the service's (`default`) with no token."""
        if self.agent is None:
            return None
        if request.profile is None:
            return self.agent.profiles.get(self.profile)
        access = check_access(self.agent, request.profile, request.token)
        if not access.allowed:
            name = request.profile if _SAFE_NAME.match(request.profile) else "<not a name>"
            logger.warning("Profile refused", profile=name, reason=access.reason)      # never the token
        return access.profile

    @staticmethod
    def _question(request: MessageReceivedRequestDTO, user_session: UserSession, profile_name: str):
        """
        (the paused run this message answers or None, whether a waiting question was discarded, a refusal code or None).
        A request with no profile and no pause_id is a legacy one: it answers the waiting question, as before.
        """
        waiting = user_session.paused
        if request.pause_id is not None:
            if waiting is None or request.pause_id != user_session.pause_id:
                return None, False, PAUSE_NOT_FOUND
            if profile_name != user_session.paused_profile:
                return None, False, PROFILE_MISMATCH              # the run stays paused and keeps its pause_id
            return waiting, False, None
        if waiting is None:
            return None, False, None
        if request.profile is None:
            return waiting, False, None
        logger.warning("A waiting question was discarded: the message had no pause_id", session_id=request.session_id)
        return None, True, None

    def _run_agent(self, request: MessageReceivedRequestDTO, user_session: UserSession, profile_name: str,
                   paused, values: dict) -> Tuple[Any, Optional[Response]]:
        extra = {"usage_reporter": self.usage_reporter} if self.usage_reporter is not None else {}
        if self.agent is not None:
            extra["agent"] = self.agent
            extra["profile"] = profile_name
            extra["inputs"] = values
            extra["client"] = request.client
            if self.cost_of is not None:
                extra["cost_of"] = self.cost_of
        agent: MessageInboundPort = self.message_service_type(
            outbound_port=self.llm_adapter,
            mcp_list=self.mcp_list,
            history=user_session.history,
            mcp_tools=self.mcp_tools,
            paused=paused,
            **extra,
        )
        text_request = text_request_of(request, user_session.name, request.correlation_id or _current_correlation_id())
        result = agent.text(text_request)
        user_session.paused = getattr(agent, "paused_run", None)   # only when the message was processed: a failure keeps the old one
        return result, getattr(agent, "last_response", None)

    def is_available(self) -> bool:
        return self.llm_adapter.is_available()

    @staticmethod
    def _failed(reason: str, apology: str, error_code: Optional[str] = None) -> MessageReceivedResponseDTO:
        # `response` is an apology that says what happened and why, so it can be spoken.
        # `message` is the technical reason.
        return MessageReceivedResponseDTO(response=apology, message=reason, success=False, error_code=error_code)

    @staticmethod
    def _refused(code: str) -> MessageReceivedResponseDTO:
        reason, apology = _REFUSALS[code]
        return MessageReceivedResponseDTO(response=apology, message=reason, success=False, error_code=code)
