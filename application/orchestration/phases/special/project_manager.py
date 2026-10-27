# Phase 2 - Project Manager
# Decomposes the goal into actions and identifies required inputs per action.

from typing import Optional

from domain.value_objects.llm_request.model import GithubModels

from application.orchestration.phases.phase import PhaseSpec
from application.orchestration.support.mcp_servers import describe_servers, server_names
from application.orchestration.support.schemas import ACTIONS_SCHEMA_FILE, SchemaRef, actions_schema, schema_properties
from application.outbound.ports.mcp_ports import McpToolsPort

# --- What this phase uses ---------------------------------------------------
PHASE_ID = 2
STEP_NAME = "project_manager"
MODEL_ENV_VAR = "AI_AGENT_MODEL_PHASE_2"
DEFAULT_MODEL = GithubModels.GPT_4_1
PROMPT_FILE = "prompts/2_project_manager.txt"
FORMAT_NAME = "project_manager_phase2_response_format"
INTENT = ("decision_support", ("information_request",), 0.9)
REQUIRED = ("actions", "next_step", "task_category_complexity")
ACTIONS_SCHEMA = ACTIONS_SCHEMA_FILE            # the "actions" property; it also takes the MCP server names
SCHEMAS = {
    "next_step": SchemaRef("general/next_steps/next_step.schema.json", "next_step"),
    "task_category_complexity": SchemaRef("general/task_category/task_category.complexity.schema.json", "complexity"),
}
# -----------------------------------------------------------------------------


def _properties(mcp_list: list):
    others = schema_properties(SCHEMAS)
    return {
        "actions": actions_schema(server_names(mcp_list), ACTIONS_SCHEMA),
        "next_step": others["next_step"],
        "task_category_complexity": others["task_category_complexity"],
    }


def make_project_manager(mcp_list: list, mcp_tools: Optional[McpToolsPort] = None) -> PhaseSpec:
    return PhaseSpec(
        id=PHASE_ID,
        step_name=STEP_NAME,
        prompt_file=PROMPT_FILE,
        model=DEFAULT_MODEL,
        intent=INTENT,
        format_name=FORMAT_NAME,
        required=REQUIRED,
        properties=lambda: _properties(mcp_list),
        build_input=lambda state: _build_input(state, mcp_list, mcp_tools),
        apply=_apply,
    )


def _build_input(state, mcp_list: list, mcp_tools: Optional[McpToolsPort]) -> dict:
    user_message = {
        "user_goal": state.user_goal,
        "task_category": state.task_category,
        "available_mcp_servers": describe_servers(mcp_list, mcp_tools),
    }
    if state.history:
        user_message["conversation_history"] = state.history_as_dicts()
    if state.answers:
        user_message["user_answers"] = state.answers_as_dicts()
    return user_message


def _apply(state, response):
    state.actions = response.actions
    state.next_step = response.next_step
