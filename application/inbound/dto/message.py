from enum import Enum
from typing import Optional, Union, Literal, Any, List, Dict
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

from application.inbound.dto.base_request import BaseRequestDTO, BaseResponseDTO
from domain.value_objects.movement.movement import Movement

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
    # Whether the movement flow announces a movement that goes ahead (Brain's setting, sent with every message).
    speak_movements: bool = True


class TextResponseDTO(BaseResponseDTO):
    content: str
    is_final: bool = False
    # The movement sequence, in execution order: the movement flow's validated one, or the gesture of the reply.
    movements: List[Movement] = Field(default_factory=list)
    # True when `movements` are an expressive gesture that goes with `content`, not movements the user asked for.
    gesture: bool = False
    # True when `content` is a question for the user: the flow is paused until they answer.
    awaiting_user_input: bool = False
    # The flow that produced the answer: identification, conversation, special or movement.
    flow: str = ""

class AudioRequestDTO(BaseRequestDTO):
    data: str  # Base64
    format: Literal["pcm16", "opus"] = "pcm16"
    sample_rate: int = 24000


class AudioResponseDTO(BaseResponseDTO):
    data: str  # Base64
    format: Literal["pcm16", "opus"] = "pcm16"
    sample_rate: int = 24000
    transcript: Optional[str] = None
