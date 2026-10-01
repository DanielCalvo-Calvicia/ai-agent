# ===============================================
#  CONVERSATION FLOW
#  The agent that talks with the user: triage, plan, validate, execute, write, polish.
#  Its phases live in phases/common (shared with the other flows) and phases/conversation_flow.
# ===============================================

from typing import List, Optional

from application.orchestration.flows.action_executor import ActionExecutor
from application.orchestration.flows.fast_path import applies as fast_path_applies
from application.orchestration.engine.flow import Flow, FlowContext
from application.orchestration.state.flow_state import FlowState
from application.orchestration.state.paused_run import FlowResult
from application.orchestration.phases.phase import PhaseSpec, Step
from application.orchestration.phases.common import triage
from application.orchestration.phases.conversation_flow import draft_writer, editor_in_chief, project_manager, safety_gate
from shared_logging import get_logger

logger = get_logger(__name__)

FLOW_NAME = "conversation-flow"

ACTION_EXECUTOR_STEP_NAME = "action_executor"      # runs phases 4, 5 and 6 for every planned action


def build_steps(context: FlowContext) -> List[Step]:
    """The phases of the agent, in execution order."""
    runner = context.runner
    executor = ActionExecutor(runner, context.mcp_list, context.mcp_tools)

    def llm_phase(spec: PhaseSpec):
        return lambda state: spec.apply(state, runner.run_phase(spec, state))

    def needs_user_input(state: FlowState) -> bool:
        return state.needs_user_input()

    return [
        # 1 - Classifies intent, extracts user goal and task category. It never pauses for a message motion-flow
        # already handled (robot_context): whatever is missing for the movement was asked there.
        Step(triage.STEP_NAME, llm_phase(triage.TRIAGE),
             pause_if=lambda state: state.needs_user_input() and state.robot_context is None,
             phase_id=triage.PHASE_ID, retry_on_status=True),
        # 2 - Decomposes the goal into actions and identifies required inputs per action.
        Step(project_manager.STEP_NAME, llm_phase(project_manager.make_project_manager(context.mcp_list, context.mcp_tools)),
             pause_if=needs_user_input, phase_id=project_manager.PHASE_ID, retry_on_status=True),
        # 3 - Validates actions for safety and decides if user confirmation is needed.
        Step(safety_gate.STEP_NAME, llm_phase(safety_gate.SAFETY_GATE), pause_if=needs_user_input,
             phase_id=safety_gate.PHASE_ID, retry_on_status=True),
        # 4, 5, 6 - Every action runs in dependency order, one LLM request each:
        #           the worker (4), the MCP operator (5) and, for MCP results, the data engineer (6).
        Step(ACTION_EXECUTOR_STEP_NAME, executor.run),
        # 7 - Synthesizes all action outputs into a first draft of the user response.
        # The fast path (below) jumps straight here from triage for a plain, simple reply, skipping
        # 2/3/4-6: nothing was planned, so there is nothing to validate or execute.
        Step(draft_writer.STEP_NAME, llm_phase(draft_writer.DRAFT_WRITER)),
        # 8 - Polishes the draft and produces the final response for the user.
        Step(editor_in_chief.STEP_NAME, llm_phase(editor_in_chief.EDITOR_IN_CHIEF),
             phase_id=editor_in_chief.PHASE_ID, retry_on_status=True),
    ]


def jump_after(step: Step, state: FlowState) -> Optional[str]:
    """
    After triage, a plain reply skips planning and action execution and goes straight to the draft writer.
    So does a message motion-flow already handled: there is nothing to plan, only what the robot does to say.
    """
    if step.name != triage.STEP_NAME:
        return None

    if state.robot_context is not None:
        logger.info("Robot context: skipping planning and action execution, the reply says what the robot does")
        return draft_writer.STEP_NAME

    if fast_path_applies(state):
        logger.info("Fast path: skipping planning and action execution for a simple reply")
        return draft_writer.STEP_NAME

    return None


def build_result(state: FlowState) -> FlowResult:
    return FlowResult(reply=state.final_text())


CONVERSATION_FLOW = Flow(
    name=FLOW_NAME,
    build_steps=build_steps,
    jump_after=jump_after,
    build_result=build_result,
)
