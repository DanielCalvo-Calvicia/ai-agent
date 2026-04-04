from dataclasses import dataclass
from typing import Dict

from domain.entities.conversation import Conversation

@dataclass
class ConversationHistory:
    conversation_history: Dict[str, Conversation]

    def __init__(self):
        self.conversation_history = {}

    def add_conversation(self, conversation: Conversation) -> None:
        self.conversation_history[conversation.id] = conversation