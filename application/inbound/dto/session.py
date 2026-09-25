from enum import Enum
from typing import Optional, Union, Literal, Any, List, Dict
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

from application.inbound.dto.base_request import BaseRequestDTO, BaseResponseDTO
from application.orchestration.robot_directive import RobotDirective

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

class MessageReceivedResponseDTO(BaseResponseDTO):
    response: str
    directive: Optional[RobotDirective] = None