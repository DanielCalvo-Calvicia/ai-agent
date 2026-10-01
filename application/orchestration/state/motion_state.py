# ===============================================
#  MOTION FLOW STATE
#  What motion-flow's phases read and write while one message travels through it:
#  everything of the shared FlowState (triage fills it), plus the movement sequence.
# ===============================================

from dataclasses import dataclass, field
from typing import List, Optional

from application.orchestration.state.flow_state import FlowState
from domain.value_objects.motion.movement import Movement


@dataclass
class MotionFlowState(FlowState):
    # Whether the user asked for an arm movement (even with a detail still missing).
    motion_requested: bool = False
    # The sequence the planner wrote, then the one the validator kept (empty when it refused it).
    movements: List[Movement] = field(default_factory=list)
    # A sentence the robot can say when the validator refused the sequence.
    motion_rejection: Optional[str] = None
