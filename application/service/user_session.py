from dataclasses import dataclass, field
from typing import List, Optional

from application.runtime.state.history import HistoryEntry, messages_of
from application.runtime.state.paused_run import PausedRun

from domain.entities.llm_response.response import Response
from domain.value_objects.llm_request.message import Message


@dataclass
class UserSession:
    """One started session: who it belongs to and the last requests the agent remembers (one entry each)."""
    session_id: str
    username: str
    email: Optional[str] = None
    name: Optional[str] = None        # the chat's name; groups its messages in the cost tracker
    entries: List[HistoryEntry] = field(default_factory=list)
    # The run that stopped to ask the user something. The next message is checked as its answer.
    paused: Optional[PausedRun] = None
    # The id of that question and the profile that asked it: the answer must carry the id and name the same profile.
    pause_id: Optional[str] = None
    paused_profile: Optional[str] = None

    @property
    def history(self) -> List[Message]:
        """The remembered exchanges as the steps read them (a user message, then its reply), oldest first."""
        return messages_of(self.entries)

    def remember(self, user_text: str, reply: str, max_turns: int, response: Optional[Response] = None) -> None:
        """Keeps the last `max_turns` requests, each with its input, its reply and, when the run had one, its Response."""
        self.entries.append(HistoryEntry(user_text, reply, response))

        keep = max(max_turns, 0)
        if len(self.entries) > keep:
            del self.entries[:len(self.entries) - keep]
