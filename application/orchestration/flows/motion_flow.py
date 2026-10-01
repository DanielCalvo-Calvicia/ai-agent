# ===============================================
#  MOTION FLOW
#  The agent that turns what the user said into an ordered list of arm movements:
#  triage, plan the movements (asking the user when a detail is missing), validate the sequence.
#  It only decides: Brain is the one that runs the movements. Triage is shared with conversation-flow
#  (phases/common); the planner and the validator are this flow's own (phases/motion_flow).
# ===============================================

from typing import List

from application.orchestration.engine.flow import Flow, FlowContext
from application.orchestration.state.motion_state import MotionFlowState
from application.orchestration.state.paused_run import FlowResult
from application.orchestration.phases.phase import PhaseSpec, Step
from application.orchestration.phases.common import triage
from application.orchestration.phases.motion_flow import motion_planner, motion_validator

FLOW_NAME = "motion-flow"


def build_steps(context: FlowContext) -> List[Step]:
    """The phases of the agent, in execution order."""
    runner = context.runner

    def llm_phase(spec: PhaseSpec):
        return lambda state: spec.apply(state, runner.run_phase(spec, state))

    return [
        # 1 - Classifies the message. Shared with conversation-flow, so both show up the same way in Langfuse.
        # It never pauses here: only the planner decides whether a detail is missing.
        Step(triage.STEP_NAME, llm_phase(triage.TRIAGE), phase_id=triage.PHASE_ID, retry_on_status=True),
        # 20 - Writes the movement list. Pauses to ask the user when the arm or the degrees are missing.
        Step(motion_planner.STEP_NAME, llm_phase(motion_planner.MOTION_PLANNER),
             pause_if=lambda state: state.needs_user_input(), phase_id=motion_planner.PHASE_ID, retry_on_status=True),
        # 21 - Checks the list (plain code). One bad movement refuses the whole sequence.
        Step(motion_validator.STEP_NAME, motion_validator.run, phase_id=motion_validator.PHASE_ID),
    ]


def build_result(state: MotionFlowState) -> FlowResult:
    """The refusal to say out loud (when there is one) and the movements to run, in order."""
    return FlowResult(reply=state.motion_rejection or "", movements=tuple(state.movements))


MOTION_FLOW = Flow(
    name=FLOW_NAME,
    build_steps=build_steps,
    build_result=build_result,
    new_state=lambda message, history: MotionFlowState(message=message, history=history),
)
