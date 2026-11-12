# ===============================================
#  TOOL CALLER
#  The fast flow (ADR-019, T-08.5): calls, in code, the tool the tool selector chose and keeps its answer as the output of the
#  action. No model runs here and the answer is not rewritten.
#
#  It runs at most ONE tool call and only a read-only tool: the fast path has no safety gate step, so the check is here
#  (`read_only_only`, T-08.4). Whatever the selector wrote that is not a tool call (a `generation` action: small talk, a refusal) is left for
#  the writer. This file names no server and no tool.
# ===============================================

from typing import Optional

from application.ports.outbound.mcp_ports import McpToolsPort
from application.ports.outbound.tool_wait_budget import tool_wait_budget
from application.ports.outbound.tool_failures import watch_tool_failures
from application.runtime.state.flow_state import FlowState
from application.runtime.step.registry import register_step
from application.support.tools.action_tree import MCP_ACTION_TYPE, action_type_of, in_execution_order
from application.support.tools.direct_call import call_directly, direct_call_of
from domain.entities.llm_response.action import Action
from domain.value_objects.llm_response.action.output import create_output

# --- What this step uses ----------------------------------------------------
LLM = False                              # plain code: no model, no prompt
PHASE_ID = 52
STEP_NAME = "tool_caller"
# -----------------------------------------------------------------------------
register_step(__name__, "code")

MAX_TOOL_WAIT_SECONDS = 60               # the same 60 s of tool waiting as the action executor (ADR-011); a test keeps them equal

ONE_CALL_ONLY = "The fast path makes one tool call per request, so this one was not made: it has to be asked for separately."
INCOMPLETE_CALL = "The tool call was not complete (the tool or its arguments are missing), so it was not made."
NO_TOOLS = "No tool can be called here."
NO_RESULT = "The tool did not answer."


def build_step(runner, mcp_list: list, mcp_tools: Optional[McpToolsPort] = None, declarations: Optional[dict] = None):
    """The function a flow runs for this step (runtime/step/build.py)."""
    return ToolCaller(runner, mcp_list, mcp_tools).run


class ToolCaller:
    def __init__(self, runner, mcp_list: list, mcp_tools: Optional[McpToolsPort]) -> None:
        self.runner = runner
        self.mcp_list = mcp_list
        self.mcp_tools = mcp_tools

    def run(self, state: FlowState) -> None:
        with tool_wait_budget(MAX_TOOL_WAIT_SECONDS):
            made = False
            for action in in_execution_order(state.actions or []):
                if action_type_of(action) != MCP_ACTION_TYPE:
                    continue                                   # not a tool call: the writer reads it as it is
                action.output = None                           # what the selector expected is replaced by what the tool answers
                action.error = None
                if made:
                    action.mark_failed(ONE_CALL_ONLY)
                    continue
                made = True
                output, error = self._call(action)
                if output:
                    _keep(action, output)
                else:
                    action.mark_failed(error or NO_RESULT)

    def _call(self, action: Action) -> tuple:
        direct = direct_call_of(action)
        if direct is None:
            return "", INCOMPLETE_CALL
        if self.mcp_tools is None:
            return "", NO_TOOLS
        with watch_tool_failures() as tool_failures:
            try:
                return call_directly(direct, self.mcp_tools, self.mcp_list, read_only_only=True)
            except NotImplementedError:
                return "", NO_TOOLS
            finally:
                for call in tool_failures.calls:
                    self.runner.metrics.record_tool_call(call)


def _keep(action: Action, output: str) -> None:
    try:
        action.mark_success(output)
    except Exception:
        action.output = create_output(output)                  # the action already carried an error from the plan: keep the result anyway
