# ===============================================
#  EXPRESSION FLOW
#  The agent that gives a spoken reply its arm gesture: read the emotion of the exchange (what the user said and what the
#  robot answers), then build random movements shaped by it. It never runs on its own: the router runs it after the
#  conversation and special flows, with their reply (see router.py). It only decides: Brain starts the gesture when the
#  robot starts to speak and is the one that runs it.
# ===============================================

from typing import List

from application.orchestration.engine.flow import Flow, FlowContext
from application.orchestration.phases.expression import emotion_reader, gesture_builder
from application.orchestration.phases.phase import PhaseSpec, Step
from application.orchestration.state.expression_state import ExpressionFlowState, as_expression
from application.orchestration.state.flow_state import FlowState
from application.orchestration.state.paused_run import FlowResult

FLOW_NAME = "expression"


def build_steps(context: FlowContext) -> List[Step]:
    runner = context.runner

    def llm_phase(spec: PhaseSpec):
        return lambda state: spec.apply(state, runner.run_phase(spec, state))

    return [
        # 30 - Names the emotion of the exchange, how strong it is and, maybe, a few movements of its own.
        Step(emotion_reader.STEP_NAME, llm_phase(emotion_reader.EMOTION_READER), phase_id=emotion_reader.PHASE_ID),
        # 31 - Builds the gesture (plain code, random, shaped by the emotion).
        Step(gesture_builder.STEP_NAME, gesture_builder.run, phase_id=gesture_builder.PHASE_ID),
    ]


def build_result(state: FlowState) -> FlowResult:
    """The gesture. The reply is not this flow's: the router keeps the one the answering flow wrote."""
    state = as_expression(state)
    return FlowResult(reply="", movements=tuple(state.movements), gesture=True)


EXPRESSION_FLOW = Flow(
    name=FLOW_NAME,
    build_steps=build_steps,
    build_result=build_result,
    new_state=lambda message, history: ExpressionFlowState(message=message, history=history),
)
