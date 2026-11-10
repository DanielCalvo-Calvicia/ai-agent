# ===============================================
#  HISTORY
#  What a session remembers of each request: the words of the user, the reply that was sent and the structured Response of the
#  run (PR-005 section 7, Q09-4). The steps read the exchanges as messages, exactly as when the session kept text pairs.
# ===============================================

from dataclasses import dataclass
from typing import List, Optional

from application.runtime.state.flow_state import FlowState
from application.runtime.state.paused_run import FlowResult
from domain.entities.llm_response.response import Response
from domain.value_objects.llm_request.message import Message, Role


@dataclass(frozen=True)
class HistoryEntry:
    """One request of a session. `message` and `reply` are its input and its output; `response` is the structured result of the run
    (None for an exchange remembered as text only). Never written to a log: it holds the user's words."""
    message: str
    reply: str
    response: Optional[Response] = None


def messages_of(entries: List[HistoryEntry]) -> List[Message]:
    """The exchanges as the steps read them: the user's message, then the reply when there is one."""
    messages: List[Message] = []
    for entry in entries:
        messages.append(Message(Role.USER, entry.message))
        if entry.reply.strip():
            messages.append(Message(Role.ASSISTANT, entry.reply))
    return messages


def response_of(result: FlowResult) -> Optional[Response]:
    """
    The structured Response a run ends with, or None when it has no `user_goal` (a run of plain code: the movement of a profile that
    got no classification, the gesture). A request adds a history entry only when it has one.
    """
    state = result.state
    if not isinstance(state, FlowState) or state.user_goal is None:
        return None
    return state.as_response()
