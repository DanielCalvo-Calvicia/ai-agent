from enum import Enum
from typing import Optional, Union, Literal, Any, List, Dict
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

from application.inbound.dto.base_request import BaseRequestDTO, BaseResponseDTO
from domain.value_objects.movement.movement import Movement

class StartSessionRequestDTO(BaseRequestDTO):
    username: str
    email: Optional[str] = None
    # Name of the chat, like the title of a chat in an online LLM. Its messages are grouped under it in Langfuse.
    session_name: Optional[str] = None

class StartSessionResponseDTO(BaseResponseDTO):
    session_id: str
    
class EndSessionRequestDTO(BaseRequestDTO):
    session_id: str

class EndSessionResponseDTO(BaseResponseDTO):
    success: bool

class MessageReceivedRequestDTO(BaseRequestDTO):
    session_id: str
    message: str
    # Whether the movement flow announces a movement that goes ahead (Brain's setting, sent with every message).
    speak_movements: bool = True

class MessageReceivedResponseDTO(BaseResponseDTO):
    response: str
    # The movement sequence, in execution order: the movement flow's validated one, or the gesture of the reply.
    movements: List[Movement] = Field(default_factory=list)
    # True when `movements` are an expressive gesture that goes with `response`, not movements the user asked for.
    gesture: bool = False
    # True when `response` is a question for the user: the flow is paused until they answer.
    awaiting_user_input: bool = False
    # The flow that produced the answer: identification, conversation, special or movement.
    flow: str = ""