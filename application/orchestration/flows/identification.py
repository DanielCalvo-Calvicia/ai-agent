# ===============================================
#  IDENTIFICATION FLOW
#  The first agent every message meets. It only classifies the message (triage): intent, goal, task category and
#  whether anything is missing. It never answers. The router reads task_category.domain from its state and hands
#  the message to the flow that answers. It stops to ask the user only when triage cannot classify without a detail.
# ===============================================

from typing import List

from application.orchestration.engine.flow import Flow, FlowContext
from application.orchestration.phases.identification import triage
from application.orchestration.phases.phase import PhaseSpec, Step
from application.orchestration.state.paused_run import FlowResult

FLOW_NAME = "identification"


def build_steps(context: FlowContext) -> List[Step]:
    runner = context.runner

    def llm_phase(spec: PhaseSpec):
        return lambda state: spec.apply(state, runner.run_phase(spec, state))

    return [
        # 1 - Classifies intent, extracts the user goal and the task category (its domain picks the next flow).
        Step(triage.STEP_NAME, llm_phase(triage.TRIAGE), pause_if=lambda state: state.needs_user_input(),
             phase_id=triage.PHASE_ID, retry_on_status=True),
    ]


def build_result(state) -> FlowResult:
    """Nothing to say: the state it ends with (the triage) is what the router needs."""
    return FlowResult(reply="")


IDENTIFICATION_FLOW = Flow(
    name=FLOW_NAME,
    build_steps=build_steps,
    build_result=build_result,
)
