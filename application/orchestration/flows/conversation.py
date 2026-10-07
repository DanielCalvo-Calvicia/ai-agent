# ===============================================
#  CONVERSATION FLOW
#  A plain spoken reply: a greeting, small talk or a simple question (task_category.domain = communication).
#  Nothing is planned, validated or executed, so it is only two steps and two LLM calls after identification.
#  It starts from the state identification left (intent, goal, category).
# ===============================================

from typing import List

from application.orchestration.engine.flow import Flow, FlowContext
from application.orchestration.phases.common import draft_writer, editor_in_chief
from application.orchestration.phases.phase import PhaseSpec, Step
from application.orchestration.state.flow_state import FlowState
from application.orchestration.state.paused_run import FlowResult

FLOW_NAME = "conversation"


def build_steps(context: FlowContext) -> List[Step]:
    runner = context.runner

    def llm_phase(spec: PhaseSpec):
        return lambda state: spec.apply(state, runner.run_phase(spec, state))

    return [
        # 7 - Writes the first draft of the reply.
        Step(draft_writer.STEP_NAME, llm_phase(draft_writer.DRAFT_WRITER)),
        # 8 - Polishes it into the final reply.
        Step(editor_in_chief.STEP_NAME, llm_phase(editor_in_chief.EDITOR_IN_CHIEF),
             phase_id=editor_in_chief.PHASE_ID, retry_on_status=True),
    ]


def build_result(state: FlowState) -> FlowResult:
    return FlowResult(reply=state.final_text())


CONVERSATION_FLOW = Flow(
    name=FLOW_NAME,
    build_steps=build_steps,
    build_result=build_result,
)
