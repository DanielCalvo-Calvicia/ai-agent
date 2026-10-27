import anyio.to_thread
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from application.inbound.dto.session import (
    EndSessionRequestDTO,
    MessageReceivedRequestDTO,
    StartSessionRequestDTO,
)
from application.inbound.ports.session import SessionInboundPort
from contracts.api.microservices.ai_agent.decision import MotorDirective
from contracts.api.microservices.ai_agent.session import (
    AIAgentEndSessionResponse,
    AIAgentMessageResponse,
    AIAgentStartSessionResponse,
)
from contracts.api.microservices.common.availability import AvailabilityResponse
from contracts.api.microservices.common.health_check import HealthCheckResponse
from infrastructure.inbound.http.responses import failure, success


_ACTION_LABELS = {
    "start_session": "start session",
    "end_session": "end session",
    "message_received": "process message",
}


def _openapi_responses(action: str, outcome: str, message, data: dict) -> dict:
    """The OpenAPI description of the answers of a session route."""
    return {
        200: {
            "description": outcome,
            "content": {"application/json": {"example": {
                "action": action,
                "status": "success",
                "status_code": 200,
                "message": message,
                "data": {**data, "success": True, "error_code": None},
                "timestamp": 1743850800.0,
            }}},
        },
        422: {"description": "Validation error: missing or invalid fields"},
        500: {"description": "Internal server error"},
    }


def message_data(result) -> AIAgentMessageResponse:
    """The answer of /session/message: the reply, the movements to run (the ones asked for, or the gesture of the reply) and which flow answered."""
    return AIAgentMessageResponse(
        success=result.success, response=result.response,
        message=result.message, error_code=result.error_code,
        directives=tuple(MotorDirective(arm=m.arm, degrees=m.degrees, direction=m.direction,
                                        pause_seconds=m.pause_seconds)
                         for m in result.movements),
        awaiting_user_input=result.awaiting_user_input,
        flow=result.flow or None,
        gesture=result.gesture,
    )


class SessionFastAPI:
    """HTTP routes of the agent: /session/start, /session/message, /session/end, /health and /available. Only translates between HTTP and the SessionInboundPort."""

    def __init__(self, App: FastAPI, SessionPort: SessionInboundPort):
        self.app = App
        self.session_port = SessionPort
        self.register_health_routes()
        self.register_routes()

    def register_health_routes(self):
        @self.app.get(
            "/health",
            tags=["Health"],
            summary="Service health",
            description="Answers as long as the service is up. Does not call any LLM.",
        )
        async def health():
            return success("health", "ai-agent is running", HealthCheckResponse(healthy=True))

        @self.app.get(
            "/available",
            tags=["Health"],
            summary="Service availability",
            description="Whether a language model provider is configured well enough to attempt a "
                        "call. Does not call any LLM.",
        )
        async def available():
            try:
                is_available = self.session_port.is_available()
            except Exception as e:
                return failure("check_availability", f"Failed to check availability: {str(e)}")
            reason = None if is_available else "no language model provider is configured"
            return success("check_availability", "Availability checked successfully",
                           AvailabilityResponse(is_available=is_available, reason=reason))

    def register_routes(self):
        @self.app.post(
            "/session/start",
            tags=["Session"],
            summary="Start a new session",
            description="Creates a new user session and returns a unique session ID. "
                        "The session must be started before sending messages.",
            responses=_openapi_responses(
                "start_session", "Session started successfully", "Session started successfully.",
                {"session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}),
        )
        async def start_session(Request: StartSessionRequestDTO):
            return await self._handle(
                "start_session", self.session_port.start_session, Request,
                to_data=lambda result: AIAgentStartSessionResponse(
                    success=result.success, session_id=result.session_id, message=result.message,
                    error_code=result.error_code),
            )

        @self.app.post(
            "/session/end",
            tags=["Session"],
            summary="End an existing session",
            description="Terminates a session by its ID. "
                        "After ending, the session ID can no longer be used to send messages.",
            responses=_openapi_responses(
                "end_session", "Session ended (check data.success for outcome)", "Session ended successfully.",
                {}),
        )
        async def end_session(Request: EndSessionRequestDTO):
            return await self._handle(
                "end_session", self.session_port.end_session, Request,
                to_data=lambda result: AIAgentEndSessionResponse(
                    success=result.success, message=result.message, error_code=result.error_code),
            )

        @self.app.post(
            "/session/message",
            tags=["Session"],
            summary="Send a message to an active session",
            description="Sends a user message to the AI agent within an active session. "
                        "The message is identified first and then answered by one flow (data.flow): "
                        "conversation, special or movement. data.directives are the arm movements to run, "
                        "in order. When it could not be processed, status is "
                        "'error', data.response is an apology and data.message tells why.",
            responses=_openapi_responses(
                "message_received", "Message processed (check data.success for outcome)", None,
                {"response": "The answer to your question is..."}),
        )
        async def message_received(Request: MessageReceivedRequestDTO):
            # The whole agent flow is synchronous (several LLM calls, one after another).
            # It runs in a worker thread so the event loop keeps serving other requests.
            return await self._handle(
                "message_received", self.session_port.message_received, Request,
                to_data=message_data,
                in_thread=True, error_when_not_successful=True,
            )

    async def _handle(self, action: str, call, request, to_data, in_thread: bool = False,
                      error_when_not_successful: bool = False) -> JSONResponse:
        try:
            result = await anyio.to_thread.run_sync(call, request) if in_thread else call(request)
            ok = result.success or not error_when_not_successful
            return success(action, result.message, to_data(result), ok=ok)
        except Exception as e:
            return failure(action, f"Failed to {_ACTION_LABELS[action]}: {str(e)}")
