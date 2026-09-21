from enum import Enum
from typing import Optional, Union, Literal, Any, List, Dict
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

from application.inbound.dto.base_request import BaseRequestDTO, BaseResponseDTO

class MessageType(str, Enum):
    TEXT = "text"
    AUDIO = "audio"
    STEP = "step"
    CONTROL = "control"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class InteractionStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    STREAMING = "streaming"


class ControlType(str, Enum):
    CANCEL = "cancel"
    PAUSE = "pause"
    RESUME = "resume"
    HEARTBEAT = "heartbeat"

class TextRequestDTO(BaseRequestDTO):
    session_id: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    session_name: Optional[str] = None


class TextResponseDTO(BaseResponseDTO):
    content: str
    is_final: bool = False

class AudioRequestDTO(BaseRequestDTO):
    data: str  # Base64
    format: Literal["pcm16", "opus"] = "pcm16"
    sample_rate: int = 24000


class AudioResponseDTO(BaseResponseDTO):
    data: str  # Base64
    format: Literal["pcm16", "opus"] = "pcm16"
    sample_rate: int = 24000
    transcript: Optional[str] = None
