# ===============================================
#  MOVEMENT FLOW
#  The agent that turns what the user said into an ordered list of arm movements (task_category.domain = movement):
#  plan the movements (asking the user when a detail is missing), validate the sequence.
#  It only decides: Brain is the one that runs the movements. It starts from the state identification left; the
#  planner and the validator are this flow's own (phases/movement). Whether a movement that goes ahead is announced
#  out loud is Brain's setting, sent per message (`speak_movements`).
# ===============================================

from typing import List

from application.orchestration.engine.flow import Flow, FlowContext
from application.orchestration.phases.movement import motion_planner, motion_validator
from application.orchestration.phases.phase import PhaseSpec, Step
from application.orchestration.state.flow_state import FlowState
from application.orchestration.state.motion_state import MotionFlowState, as_motion
from application.orchestration.state.paused_run import FlowResult

FLOW_NAME = "movement"


def build_steps(context: FlowContext) -> List[Step]:
    """The phases of the agent, in execution order."""
    runner = context.runner

    def llm_phase(spec: PhaseSpec):
        return lambda state: spec.apply(state, runner.run_phase(spec, state))

    return [
        # 20 - Writes the movement list and a short spoken line. Pauses to ask the user when the arm or the degrees are missing.
        Step(motion_planner.STEP_NAME, llm_phase(motion_planner.MOTION_PLANNER),
             pause_if=lambda state: state.needs_user_input(), phase_id=motion_planner.PHASE_ID, retry_on_status=True),
        # 21 - Checks the list (plain code). One bad movement refuses the whole sequence.
        Step(motion_validator.STEP_NAME, motion_validator.run, phase_id=motion_validator.PHASE_ID),
    ]


def build_result(state: FlowState) -> FlowResult:
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


MOVEMENT_FLOW = Flow(
    name=FLOW_NAME,
    build_steps=build_steps,
    build_result=build_result,
    new_state=lambda message, history: MotionFlowState(message=message, history=history),
)
