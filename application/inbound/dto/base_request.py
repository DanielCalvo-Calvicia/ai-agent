from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict


# ==========================================================
# Base Contracts (Enterprise Standard)
# ==========================================================

class BaseRequestDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID = Field(default_factory=uuid4)
    user_id: str = Field(..., min_length=3, max_length=128)
    correlation_id: Optional[str] = Field(
        default=None,
        description="Used for distributed tracing across services"
    )
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BaseResponseDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    message: Optional[str] = None
    error_code: Optional[str] = None
    correlation_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)