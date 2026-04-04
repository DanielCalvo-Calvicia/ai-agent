from dataclasses import dataclass

from domain.entities.conversation_history import ConversationHistory
from domain.entities.conversation import Conversation
from domain.entities.user import User


@dataclass
class Session:
    id: str
    user: User
    conversation_history: ConversationHistory