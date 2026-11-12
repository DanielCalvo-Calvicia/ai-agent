from enum import Enum
from typing import Optional, Union, Literal, Any, List, Dict
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
import uuid

from application.dtos.inbound.base_request import BaseRequestDTO, BaseResponseDTO
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
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    session_id: str
    message: str
    # Whether the movement flow announces a movement that goes ahead (Brain's setting, sent with every message).
    speak_movements: bool = True
    # The profile asked and its token. None: the `default` profile, which needs no token. The vendored `contracts` do not have
    # these fields yet (PR-005 section 6): ai-agent reads them from its own request model until they do.
    profile: Optional[str] = Field(default=None, max_length=64)
    token: Optional[str] = Field(default=None, max_length=256, repr=False)      # never logged
    # Fields of the state for the profile (the `Response` an earlier profile returned, or `reply` for the gesture). Data, never instructions.
    inputs: Optional[Dict[str, Any]] = None
    # `text`: only `response` (today's answer); `full`: also `output`, the Response of the run. None: the default of the profile.
    return_: Optional[Literal["text", "full"]] = Field(default=None, alias="return")
    # The id of the question this message answers, as the answer that paused returned it.
    pause_id: Optional[str] = Field(default=None, max_length=64)
    # A name for the metrics (trust-based).
    client: Optional[str] = Field(default=None, max_length=64)

class MessageReceivedResponseDTO(BaseResponseDTO):
    response: str
    # The movement sequence, in execution order: the movement flow's validated one, or the gesture of the reply.
    movements: List[Movement] = Field(default_factory=list)
    # True when `movements` are an expressive gesture that goes with `response`, not movements the user asked for.
    gesture: bool = False
    # True when `response` is a question for the user: the flow is paused until they answer.
    awaiting_user_input: bool = False
    # The flow that produced the answer: identification, conversation, special, movement or expression.
    flow: str = ""
    # Only when the request named a profile: the profile that ran.
    profile: Optional[str] = None
    # Only when the request asked `return: full` (or the profile does): the Response of the run as JSON.
    output: Optional[Dict[str, Any]] = None
    # Only when `awaiting_user_input` is true: the id to send back with the answer.
    pause_id: Optional[str] = None
    # Only when a question waiting for the user was discarded because this message had no pause_id.
    discarded_pause: bool = False