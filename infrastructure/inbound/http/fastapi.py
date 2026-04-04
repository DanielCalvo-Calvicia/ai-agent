from fastapi import FastAPI, status

from application.inbound.ports.session import SessionInboundPort
from application.inbound.dto.session import (
    StartSessionRequestDTO,
    StartSessionResponseDTO,
    EndSessionRequestDTO,
    EndSessionResponseDTO,
    MessageReceivedRequestDTO,
    MessageReceivedResponseDTO,
)

from pydantic import BaseModel
from typing import Optional, Any
import time


#---- RETURNS RESPONSES OBJECT ----#
class StandardResponse(BaseModel):
    action: str
    status: str
    status_code: int
    message: Optional[str]
    data: Optional[Any]
    timestamp: float


class SessionFastAPI:
    def __init__(self, App: FastAPI, SessionPort: SessionInboundPort):
        self.app = App
        self.session_port = SessionPort
        self.register_routes()

    #---- ROUTES ----#
    def register_routes(self):
        @self.app.post("/session/start", tags=["Session"])
        async def start_session(Request: StartSessionRequestDTO):
            return await self.start_session(Request)

        @self.app.post("/session/end", tags=["Session"])
        async def end_session(Request: EndSessionRequestDTO):
            return await self.end_session(Request)

        @self.app.post("/session/message", tags=["Session"])
        async def message_received(Request: MessageReceivedRequestDTO):
            return await self.message_received(Request)

    #---- FUNCTIONS ----#
    async def start_session(self, Request: StartSessionRequestDTO):
        try:
            result: StartSessionResponseDTO = self.session_port.start_session(Request)

            return StandardResponse(
                action="start_session",
                status="success",
                status_code=status.HTTP_200_OK,
                message=result.message,
                data=result.model_dump(),
                timestamp=time.time()
            )

        except Exception as e:
            return StandardResponse(
                action="start_session",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"Failed to start session: {str(e)}",
                data=None,
                timestamp=time.time()
            )

    async def end_session(self, Request: EndSessionRequestDTO):
        try:
            result: EndSessionResponseDTO = self.session_port.end_session(Request)

            return StandardResponse(
                action="end_session",
                status="success",
                status_code=status.HTTP_200_OK,
                message=result.message,
                data=result.model_dump(),
                timestamp=time.time()
            )

        except Exception as e:
            return StandardResponse(
                action="end_session",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"Failed to end session: {str(e)}",
                data=None,
                timestamp=time.time()
            )

    async def message_received(self, Request: MessageReceivedRequestDTO):
        try:
            result: MessageReceivedResponseDTO = self.session_port.message_received(Request)

            return StandardResponse(
                action="message_received",
                status="success",
                status_code=status.HTTP_200_OK,
                message=result.message,
                data=result.model_dump(),
                timestamp=time.time()
            )

        except Exception as e:
            return StandardResponse(
                action="message_received",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"Failed to process message: {str(e)}",
                data=None,
                timestamp=time.time()
            )