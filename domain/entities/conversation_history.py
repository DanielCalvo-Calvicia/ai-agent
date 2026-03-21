from dataclasses import dataclass
from typing import Dict

from domain.entities.conversation import Conversation

@dataclass
class ConversationHistory:
    conversation_history: Dict[int, Conversation]