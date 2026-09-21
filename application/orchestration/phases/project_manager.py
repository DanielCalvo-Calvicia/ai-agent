# Phase 2 - Project Manager
# Decomposes the goal into actions and identifies required inputs per action.

from typing import Optional

from domain.value_objects.model import GithubModels

from application.orchestration.phase import PhaseSpec
from application.orchestration.mcp_servers import describe_servers, server_names
from application.orchestration.schemas import actions_schema, property_schema
from application.outbound.ports.mcp_ports import McpToolsPort


def _properties(mcp_list: list):
    return {
        "actions": actions_schema(server_names(mcp_list)),
        "next_step": property_schema("next_step"),
        "task_category_complexity": property_schema("complexity"),
    }


def make_project_manager(mcp_list: list, mcp_tools: Optional[McpToolsPort] = None) -> PhaseSpec:
    return PhaseSpec(
        id=2,
        model=GithubModels.GPT_4_1,
        intent=("decision_support", ("information_request",), 0.9),
        format_name="project_manager_phase2_response_format",
        required=("actions", "next_step", "task_category_complexity"),
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
