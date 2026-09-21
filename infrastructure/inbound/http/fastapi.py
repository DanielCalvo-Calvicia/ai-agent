import anyio.to_thread
from fastapi import FastAPI

from application.inbound.dto.session import (
    EndSessionRequestDTO,
    MessageReceivedRequestDTO,
    StartSessionRequestDTO,
)
from application.inbound.ports.session import SessionInboundPort
from infrastructure.inbound.http.responses import StandardResponse, failure, success


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
                "data": {**data, "success": True, "error_code": None, "correlation_id": None,
                         "timestamp": "2026-04-05T10:00:00"},
                "timestamp": 1743850800.0,
            }}},
        },
        422: {"description": "Validation error: missing or invalid fields"},
        500: {"description": "Internal server error"},
    }


class SessionFastAPI:
    """HTTP routes of the agent. Only translates between HTTP and the SessionInboundPort."""

    def __init__(self, App: FastAPI, SessionPort: SessionInboundPort):
        self.app = App
        self.session_port = SessionPort
        self.register_routes()

    def register_routes(self):
        @self.app.get(
            "/health",
            tags=["Health"],
            response_model=StandardResponse,
            summary="Service health",
            description="Answers as long as the service is up. Does not call any LLM.",
        )
        async def health():
            return success("health", "ai-agent is running", {"service": "ai-agent"})

        @self.app.post(
            "/session/start",
            tags=["Session"],
            response_model=StandardResponse,
            summary="Start a new session",
            description="Creates a new user session and returns a unique session ID. "
                        "The session must be started before sending messages.",
            responses=_openapi_responses(
                "start_session", "Session started successfully", "Session started successfully.",
                {"session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "message": "Session started successfully."}),
        )
        async def start_session(Request: StartSessionRequestDTO):
            return await self._handle("start_session", self.session_port.start_session, Request)

        @self.app.post(
            "/session/end",
            tags=["Session"],
            response_model=StandardResponse,
            summary="End an existing session",
            description="Terminates a session by its ID. "
                        "After ending, the session ID can no longer be used to send messages.",
            responses=_openapi_responses(
                "end_session", "Session ended (check data.success for outcome)", "Session ended successfully.",
                {"message": "Session ended successfully."}),
        )
        async def end_session(Request: EndSessionRequestDTO):
            return await self._handle("end_session", self.session_port.end_session, Request)

        @self.app.post(
            "/session/message",
            tags=["Session"],
            response_model=StandardResponse,
            summary="Send a message to an active session",
            description="Sends a user message to the AI agent within an active session. "
                        "The agent processes the message through the full orchestration flow "
                        "and returns a response. When it could not be processed, status is "
                        "'error', data.response is empty and data.message tells why.",
            responses=_openapi_responses(
                "message_received", "Message processed (check data.success for outcome)", None,
                {"response": "The answer to your question is...", "message": None}),
        )
        async def message_received(Request: MessageReceivedRequestDTO):
            # The whole agent flow is synchronous (several LLM calls, one after another).
            # It runs in a worker thread so the event loop keeps serving other requests.
            return await self._handle("message_received", self.session_port.message_received, Request,
                                      in_thread=True, error_when_not_successful=True)

    async def _handle(self, action: str, call, request, in_thread: bool = False,
                      error_when_not_successful: bool = False) -> StandardResponse:
        try:
            result = await anyio.to_thread.run_sync(call, request) if in_thread else call(request)
            ok = result.success or not error_when_not_successful
            return success(action, result.message, result.model_dump(), ok=ok)
        except Exception as e:
            return failure(action, f"Failed to {_ACTION_LABELS[action]}: {str(e)}")
