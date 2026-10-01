# ===============================================
#  PAUSED RUN
#  A run that stopped to ask the user something, and what the pipeline
#  returns for a message.
# ===============================================

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from application.orchestration.state.flow_state import FlowState
from domain.value_objects.motion.movement import Movement

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
    """The reply for the user, the run that is still waiting for them (if any) and, for motion-flow,
    the movements to run."""
    reply: str
    paused: Optional[PausedRun] = None
    # motion-flow: the validated movement sequence, in execution order (empty when nothing is to be moved).
    movements: Tuple[Movement, ...] = ()
