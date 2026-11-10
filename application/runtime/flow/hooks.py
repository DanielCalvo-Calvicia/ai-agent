# ===============================================
#  HOOKS
#  The fixed list of names a flow file may use for what is not a step: `on_pause` and `on_resume` (what the engine does when a
#  step asks the user and when the user answers: phases 99 and 9) and the result of the flow, which is built from the step named
#  in `result_from`. A flow carries `on_pause` and `on_resume` only when one of its steps can ask. The state a flow starts
#  with follows its steps: a flow with the motion planner starts a MotionFlowState, one with the emotion reader an ExpressionFlowState.
# ===============================================

from typing import Callable, Dict, Iterable, List, Optional, Type

from application.runtime.state.expression_state import ExpressionFlowState, as_expression
from application.runtime.state.flow_state import FlowState
from application.runtime.state.motion_state import MotionFlowState, as_motion
from application.runtime.state.paused_run import FlowResult
from domain.value_objects.llm_request.message import Message

USER_CLARIFICATION = "user_clarification"    # on_pause: turn the missing inputs into a question (phase 99)
ANSWER_CHECKER = "answer_checker"            # on_resume: decide whether the next message answers it (phase 9)
HOOKS = (USER_CLARIFICATION, ANSWER_CHECKER)


# -----------------------------------------------
#  THE RESULT OF A FLOW (the builders of the old Python flows, unchanged)
# -----------------------------------------------

def reply_of_the_state(state: FlowState) -> FlowResult:
    """The final text the last writer left: conversation and special."""
    return FlowResult(reply=state.final_text())


def nothing_to_say(state: FlowState) -> FlowResult:
    """The identification flow only classifies: the state it ends with is what the caller needs."""
    return FlowResult(reply="")


def movements_of_the_state(state: FlowState) -> FlowResult:
    """
    What to say and the movements to run, in order. A refusal is always said. Movements that go ahead are
    announced only when `speak_movements` is on. When nothing moves and nothing was refused (the message was not
    a movement after all), the planner's line is said: the user must hear something.
    """
    state = as_motion(state)
    movements = tuple(state.movements)
    if state.motion_rejection:
        reply = state.motion_rejection
    elif movements and not state.speak_movements:
        reply = ""
    else:
        reply = state.spoken_reply

    return FlowResult(reply=reply, movements=movements)


def gesture_of_the_state(state: FlowState) -> FlowResult:
    """The gesture. The reply is not this flow's: the client keeps the one the answering profile wrote."""
    state = as_expression(state)
    return FlowResult(reply="", movements=tuple(state.movements), gesture=True)


# The builder of a flow is the one of its `result_from` step; a step that is not here gives the final text.
RESULT_BUILDERS: Dict[str, Callable[[FlowState], FlowResult]] = {
    "triage_specialist": nothing_to_say,
    "motion_validator": movements_of_the_state,
    "gesture_builder": gesture_of_the_state,
}


def result_builder(result_from: Optional[str]) -> Callable[[FlowState], FlowResult]:
    return RESULT_BUILDERS.get(result_from or "", reply_of_the_state)


# -----------------------------------------------
#  THE STATE A FLOW STARTS WITH
# -----------------------------------------------

STATE_OF_STEP: Dict[str, Type[FlowState]] = {
    "motion_planner": MotionFlowState,
    "emotion_reader": ExpressionFlowState,
}


def state_factory(step_names: Iterable[str]) -> Callable[[str, List[Message]], FlowState]:
    for name in step_names:
        if name in STATE_OF_STEP:
            cls = STATE_OF_STEP[name]
            return lambda message, history: cls(message=message, history=history)
    return lambda message, history: FlowState(message=message, history=history)
