import time
from typing import Any, Optional

from fastapi import status
from pydantic import BaseModel, Field


class StandardResponse(BaseModel):
    """Unified API response wrapper for all endpoints: action / status / status_code / message / data / timestamp."""
    action: str = Field(..., description="The action that was performed", examples=["start_session"])
    status: str = Field(..., description="Result status", examples=["success", "error"])
    status_code: int = Field(..., description="HTTP status code", examples=[200, 500])
    message: Optional[str] = Field(None, description="Human-readable result message")
    data: Optional[Any] = Field(None, description="Response payload")
    timestamp: float = Field(..., description="Unix epoch timestamp of the response")


def success(action: str, message: Optional[str], data: Any, ok: bool = True) -> StandardResponse:
    """`ok=False` reports an error status for a request that was understood but not carried out."""
    return StandardResponse(
        action=action,
        status="success" if ok else "error",
        status_code=status.HTTP_200_OK,
        message=message,
        data=data,
        timestamp=time.time(),
    )


def failure(action: str, message: str) -> StandardResponse:
    return StandardResponse(
        action=action,
        status="error",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message=message,
        data=None,
        timestamp=time.time(),
    )
