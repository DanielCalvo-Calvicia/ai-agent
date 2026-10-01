# Phase 21 - Motion Validator
# Checks that the movement sequence the planner wrote can be done. Plain code, no LLM call, so it is
# cheap and always gives the same answer. One bad movement refuses the whole sequence: half of a
# choreography is never sent. A refusal carries a sentence the robot can say out loud.

import math
from typing import List, Optional

from domain.value_objects.motion.movement import ARMS, DIRECTIONS, Movement

from application.orchestration.state.motion_state import MotionFlowState

# --- What this phase uses ---------------------------------------------------
LLM = False                              # no model, no prompt, no schema
PHASE_ID = 21
STEP_NAME = "motion_validator"
MAX_MOVEMENTS = 10                       # movements in one sequence
MAX_DEGREES_PER_MOVEMENT = 360.0         # one movement, in either sign
MAX_TOTAL_ROTATION = 1440.0              # the sum of |degrees| of the whole sequence
NO_MOVEMENT_UNDERSTOOD = "I did not understand which movement you want. Which arm, and how many degrees?"
TOO_MANY_MOVEMENTS = f"That is too many movements in one go. I can do up to {MAX_MOVEMENTS} at a time."
UNKNOWN_ARM = f"I can only move my {' or '.join(ARMS)} arm."
UNKNOWN_DIRECTION = f"A movement can only go {' or '.join(DIRECTIONS)}."
NOT_A_NUMBER = "I could not tell how many degrees to move."
ZERO_DEGREES = "A movement of zero degrees does nothing."
CONTRADICTORY = "A negative number of degrees in the reverse direction is ambiguous. Tell me it again, please."
TOO_FAR = f"I cannot turn an arm more than {MAX_DEGREES_PER_MOVEMENT:g} degrees in one movement."
TOO_MUCH_IN_TOTAL = f"That sequence turns the arms more than {MAX_TOTAL_ROTATION:g} degrees in total, which is too much."
# -----------------------------------------------------------------------------


def refusal_for(movements: List[Movement]) -> Optional[str]:
    """Why the sequence cannot be done (a sentence to say), or None when every movement and the whole sequence are fine."""
    if not movements:
        return NO_MOVEMENT_UNDERSTOOD
    if len(movements) > MAX_MOVEMENTS:
        return TOO_MANY_MOVEMENTS

    for movement in movements:
        if movement.arm not in ARMS:
            return UNKNOWN_ARM
        if movement.direction not in DIRECTIONS:
            return UNKNOWN_DIRECTION
        if math.isnan(movement.degrees) or math.isinf(movement.degrees):
            return NOT_A_NUMBER
        if movement.degrees == 0:
            return ZERO_DEGREES
        if movement.degrees < 0 and movement.direction == "reverse":
            return CONTRADICTORY
        if abs(movement.degrees) > MAX_DEGREES_PER_MOVEMENT:
            return TOO_FAR

    if sum(abs(movement.degrees) for movement in movements) > MAX_TOTAL_ROTATION:
        return TOO_MUCH_IN_TOTAL

    return None


def run(state: MotionFlowState) -> None:
    """A message that asked for no movement passes with nothing to move. Otherwise the sequence is kept or refused."""
    if not state.motion_requested:
        state.movements = []
        return

    reason = refusal_for(state.movements)
    if reason:
        state.movements = []
        state.motion_rejection = reason
