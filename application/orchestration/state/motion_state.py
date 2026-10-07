# ===============================================
#  MOTION FLOW STATE
#  What the movement flow's phases read and write while one message travels through it:
#  everything of the shared FlowState (the identification flow's triage filled it), plus the movement sequence.
# ===============================================

from dataclasses import dataclass, field
from typing import List, Optional

from application.orchestration.state.flow_state import FlowState
from domain.value_objects.movement.movement import Movement


@dataclass
class MotionFlowState(FlowState):
    # Whether the user asked for an arm movement (even with a detail still missing).
    motion_requested: bool = False
    # The sequence the planner wrote, then the one the validator kept (empty when it refused it).
    movements: List[Movement] = field(default_factory=list)
    # A sentence the robot can say when the validator refused the sequence.
    motion_rejection: Optional[str] = None
    # The planner's short spoken line (what the robot is about to do, or why it cannot).
    spoken_reply: str = ""
    # Whether a movement that goes ahead is announced out loud. Brain decides (its setting) and sends it per message.
    speak_movements: bool = True


def as_motion(state: FlowState) -> MotionFlowState:
    """
    The movement flow's state. Steps are typed with the shared FlowState, but this flow always builds a
    MotionFlowState (see flows/movement.py), so anything else is a wiring mistake.
    """
    if not isinstance(state, MotionFlowState):
        raise TypeError(f"the movement flow needs a MotionFlowState, got {type(state).__name__}")
    return state
