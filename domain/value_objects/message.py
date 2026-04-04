from dataclasses import dataclass
from enum import Enum
from typing import Literal


ErrMessageEmpty = ValueError("Message content cannot be empty")

class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

@dataclass(frozen=True)
class Message:
    role: Role
    content: str

    def __post_init__(self):
        if not self.content.strip():
            raise ErrMessageEmpty
        
def create_message(role: Role, content: str) -> Message:
    return Message(role=role, content=content)