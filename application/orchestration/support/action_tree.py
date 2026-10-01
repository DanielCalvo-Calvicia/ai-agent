# ===============================================
#  ACTION TREE
#  Helpers to look inside the tree of actions the project manager plans.
# ===============================================

from typing import Any, Dict, List

from domain.entities.action import Action

MCP_ACTION_TYPE = "mcp_tool_call"

BLOCKED_BY_CONFIRMATION = "Execution blocked: requires user confirmation before running MCP tools."


def subactions_of(action: Action) -> List[Action]:
    """
    The subactions of an action as a flat list.
    Handles both dict and list storage since the Python model uses dict
    but the JSON schema defines an array.
    """
    if not action.subactions:
        return []
    if isinstance(action.subactions, dict):
        return list(action.subactions.values())
    if isinstance(action.subactions, list):
        return list(action.subactions)
    return []


def action_type_of(action: Action) -> str | None:
    return action.action_type.get_value() if action.action_type else None


def with_outputs(base: Dict[str, Any], dependency_outputs: Dict[str, str], subaction_outputs: Dict[str, str]) -> Dict[str, Any]:
    """`base` plus the results of the actions this one needs (and of its subactions, when it has any)."""
    context = dict(base)
    context["dependency_outputs"] = dependency_outputs
    if subaction_outputs:
        context["subaction_outputs"] = subaction_outputs
    return context


def mark_mcp_actions_blocked(actions: List[Action]) -> None:
    """Marks every MCP tool-call action in the tree as failed with a confirmation-blocked message. Subactions first."""
    for action in actions:
        mark_mcp_actions_blocked(subactions_of(action))
        if action_type_of(action) == MCP_ACTION_TYPE:
            action.mark_failed(BLOCKED_BY_CONFIRMATION)


def in_execution_order(actions: List[Action]) -> List[Action]:
    """Every action of the tree, each parent after its subactions, in plan order."""
    ordered: List[Action] = []
    for action in actions:
        ordered.extend(in_execution_order(subactions_of(action)))
        ordered.append(action)
    return ordered
