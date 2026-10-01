from dataclasses import dataclass, field
from typing import List, Optional

from application.orchestration.state.paused_run import PausedRun

from domain.value_objects.message import Message, Role


@dataclass
class UserSession:
    """One started session: who it belongs to and the last exchanges the agent remembers."""
    session_id: str
    username: str
    email: Optional[str] = None
    name: Optional[str] = None        # the chat's name; groups its messages in the cost tracker
    history: List[Message] = field(default_factory=list)
    # The run that stopped to ask the user something. The next message is checked as its answer.
    paused: Optional[PausedRun] = None

    def remember(self, user_text: str, reply: str, max_turns: int) -> None:
        """Keeps the last `max_turns` exchanges (a user message and its reply each)."""
        self.history.append(Message(Role.USER, user_text))
        if reply.strip():
            self.history.append(Message(Role.ASSISTANT, reply))

        keep = 2 * max(max_turns, 0)
        if len(self.history) > keep:
            del self.history[:len(self.history) - keep]
