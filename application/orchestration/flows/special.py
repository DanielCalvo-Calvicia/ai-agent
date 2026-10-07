# ===============================================
#  SPECIAL FLOW
#  Everything that is not a plain reply and not a movement: a task that needs a plan, several steps, a document
#  or a tool. Plan, check safety, execute the actions, write the draft, polish it. It starts from the state
#  identification left (intent, goal, category).
# ===============================================

from typing import List

from application.orchestration.engine.flow import Flow, FlowContext
from application.orchestration.flows.action_executor import ActionExecutor
from application.orchestration.phases.common import draft_writer, editor_in_chief
from application.orchestration.phases.phase import PhaseSpec, Step
from application.orchestration.phases.special import project_manager, safety_gate
from application.orchestration.state.flow_state import FlowState
from application.orchestration.state.paused_run import FlowResult

FLOW_NAME = "special"

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
        Step(draft_writer.STEP_NAME, llm_phase(draft_writer.DRAFT_WRITER)),
        # 8 - Polishes the draft and produces the final response for the user.
        Step(editor_in_chief.STEP_NAME, llm_phase(editor_in_chief.EDITOR_IN_CHIEF),
             phase_id=editor_in_chief.PHASE_ID, retry_on_status=True),
    ]


def build_result(state: FlowState) -> FlowResult:
    return FlowResult(reply=state.final_text())


SPECIAL_FLOW = Flow(
    name=FLOW_NAME,
    build_steps=build_steps,
    build_result=build_result,
)
