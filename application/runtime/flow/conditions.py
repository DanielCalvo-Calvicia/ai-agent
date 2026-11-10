# ===============================================
#  CONDITIONS
#  The fixed list of named conditions a flow file may use in `pause_if`. A developer writes one here in Python; a flow cannot
#  invent one (Q07-2). A condition reads the state a step just wrote and says whether the flow must stop and ask the user.
# ===============================================

from typing import Callable, Dict

from application.runtime.state.flow_state import FlowState


def needs_user_input(state: FlowState) -> bool:
    """The step left a question for the user (a detail is missing)."""
    return state.needs_user_input()


CONDITIONS: Dict[str, Callable[[FlowState], bool]] = {
    "needs_user_input": needs_user_input,
}
