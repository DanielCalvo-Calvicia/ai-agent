# ===============================================
#  PAUSED RUN
#  A run that stopped to ask the user something, and what the pipeline
#  returns for a message.
# ===============================================

from dataclasses import dataclass, field
from typing import List, Optional

from application.orchestration.flow_state import FlowState

INPUT = "input"                  # the assistant asked for information
CONFIRMATION = "confirmation"    # the assistant asked to confirm an action


@dataclass
class PausedRun:
    """Everything needed to continue where the flow stopped, without planning again."""
    state: FlowState
    step_index: int                       # the step that left the flow waiting
    kind: str                             # INPUT or CONFIRMATION
    question: str                         # what the user was told
    requested_items: List[str] = field(default_factory=list)


@dataclass
class FlowResult:
    """The reply for the user, and the run that is still waiting for them (if any)."""
    reply: str
    paused: Optional[PausedRun] = None
