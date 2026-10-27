# ===============================================
#  EXPRESSION FLOW STATE
#  What the expression flow's phases read and write while one reply is given a gesture: the exchange (what the user
#  said and what the robot answers), the emotion found in it and the movements built from it.
# ===============================================

from dataclasses import dataclass, field
from typing import List

from application.orchestration.state.flow_state import FlowState
from domain.operations.gesture import DEFAULT_EMOTION, DEFAULT_INTENSITY
from domain.value_objects.movement.movement import Movement


@dataclass
class ExpressionFlowState(FlowState):
    # What the robot answers (the user's message is `message`).
    reply: str = ""
    # How long the robot will speak that reply, in seconds (an estimate from its text).
    speech_seconds: float = 0.0
    # What the emotion reader found in the exchange.
    emotion: str = DEFAULT_EMOTION
    intensity: int = DEFAULT_INTENSITY
    # Movements the emotion reader suggested on its own (optional, a few).
    improvised: List[Movement] = field(default_factory=list)
    # The gesture the builder made (empty when the validator refused it).
    movements: List[Movement] = field(default_factory=list)


def as_expression(state: FlowState) -> ExpressionFlowState:
    """The expression flow's state. Its flow always builds one (see flows/expression.py), so anything else is a wiring mistake."""
    if not isinstance(state, ExpressionFlowState):
        raise TypeError(f"the expression flow needs an ExpressionFlowState, got {type(state).__name__}")
    return state
