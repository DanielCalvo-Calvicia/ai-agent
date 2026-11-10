# Phase 31 - Gesture Builder
# Makes the arm gesture that goes with a spoken reply, from the emotion the reader found. Plain code, no LLM call: the
# movements are random, shaped by the emotion (domain/operations/gesture.py). The motion validator checks the result
# as a safety net; a gesture it refuses is dropped, never sent (the reply is spoken anyway).

from application.steps.movement import motion_validator
from application.engine.state.expression_state import as_expression
from application.engine.state.flow_state import FlowState
from application.engine.support.expression_settings import new_rng
from domain.operations.gesture import build_gesture
from shared_logging import get_logger
from application.steps.registry import register_step

logger = get_logger(__name__)

# --- What this phase uses ---------------------------------------------------
LLM = False                              # no model, no prompt, no schema
PHASE_ID = 31
STEP_NAME = "gesture_builder"
# -----------------------------------------------------------------------------
register_step(__name__, "code")


def run(state: FlowState) -> None:
    state = as_expression(state)
    movements = build_gesture(
        state.emotion,
        state.intensity,
        state.improvised,
        state.speech_seconds,
        new_rng(),
        max_movements=motion_validator.MAX_MOVEMENTS,
        max_total_degrees=motion_validator.MAX_TOTAL_ROTATION,
    )

    reason = motion_validator.refusal_for(movements)
    if reason:
        logger.warning("The gesture was refused by the validator and is dropped", reason=reason, movements=len(movements))
        movements = []

    state.movements = movements
