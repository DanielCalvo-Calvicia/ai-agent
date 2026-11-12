# ===============================================
#  MESSAGE MAPPER (inbound)
#  The conversions of a message between the shapes the HTTP layer uses (the DTOs of `application/dtos/inbound`) and what the
#  application works with (the result of a run, made of domain objects). The service decides; this only converts.
# ===============================================

from typing import Any, Dict, Optional

from application.dtos.inbound.message import TextRequestDTO
from application.dtos.inbound.session import MessageReceivedRequestDTO, MessageReceivedResponseDTO


def text_request_of(request: MessageReceivedRequestDTO, session_name: Optional[str], correlation_id: Optional[str]) -> TextRequestDTO:
    """The request the message service runs, from the one the HTTP layer received."""
    return TextRequestDTO(
        request_id=request.request_id,
        user_id=request.user_id,
        # The DTO field is kept for API compatibility; the active trace is the source of truth.
        correlation_id=correlation_id,
        metadata=request.metadata,
        timestamp=request.timestamp,
        session_id=request.session_id,
        content=request.message,
        session_name=session_name,
        speak_movements=request.speak_movements,
    )


def message_response_of(result: Any, request: MessageReceivedRequestDTO, pause_id: Optional[str],
                        output: Optional[Dict[str, Any]], discarded: bool) -> MessageReceivedResponseDTO:
    """The answer of /session/message from the result of a run. `pause_id` and `output` are None when they do not apply."""
    return MessageReceivedResponseDTO(
        response=result.content, movements=list(result.movements), gesture=result.gesture,
        awaiting_user_input=result.awaiting_user_input, flow=result.flow, success=True,
        profile=request.profile, output=output, pause_id=pause_id, discarded_pause=discarded)
