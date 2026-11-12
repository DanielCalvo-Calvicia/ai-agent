# ===============================================
#  DIRECT CALL
#  A tool call whose tool and parameters are already decided is made by code, not by a model that rewrites the answer
#  (ADR-019, T-08.3). The action executor uses it for every independent MCP action; the fast flow uses it for its one.
#
#  This file names no server and no tool: it works on what an action says (`mcp_context`) and on what a tool answers.
# ===============================================

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from application.ports.outbound.mcp_ports import McpToolsPort
from application.support.tools.action_tree import MCP_ACTION_TYPE, action_type_of, subactions_of
from domain.entities.llm_response.action import Action

# The answer of a tool of the contract starts with `key: value` lines (a status, a count, a coverage...): it is already clean.
_CONTRACT_LINE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*:")


@dataclass(frozen=True)
class DirectCall:
    """The call an action describes: the tool and its parameters, as the plan wrote them."""
    tool: str
    arguments: Dict[str, Any]


def direct_call_of(action: Action) -> Optional[DirectCall]:
    """The call code can make for this action, or None when a model has to run it: an action that is not a tool call, that needs
    the result of another action (dependencies, subactions), or whose `mcp_context` is not complete."""
    if action_type_of(action) != MCP_ACTION_TYPE:
        return None
    if action.has_dependencies() or subactions_of(action):
        return None
    context = action.mcp_context
    if context is None or not context.tool_name or not isinstance(context.parameters, dict) or not context.parameters:
        return None
    return DirectCall(context.tool_name, dict(context.parameters))


NOT_READ_ONLY = "The tool {tool!r} is not marked read-only by its server, so the fast path does not run it."


def is_read_only(tool_name: str, mcp_list: list, mcp_tools: McpToolsPort) -> bool:
    """Whether a tool of one of the servers is marked read-only (the listing is the one the step sees: its scope applies)."""
    for server in mcp_list:
        for tool in mcp_tools.list_tools(server["name"]):
            if tool.name == tool_name:
                return tool.read_only
    return False


def call_directly(call: DirectCall, mcp_tools: McpToolsPort, mcp_list: Optional[list] = None, read_only_only: bool = False) -> Tuple[str, str]:
    """(output, error) of the call: the text the tool answered, untouched, or the text of its error. The adapter retries once after a
    transport error and follows the jobs of an answer (ADR-011, ADR-018): nothing is asked again here.

    `read_only_only` (the fast path, T-08.4): a tool its server does not mark as read-only is refused and no server is called. It needs
    `mcp_list`, the servers the step may use; without it nothing can be proved read-only, so the call is refused too.

    Raises NotImplementedError when the port cannot call a tool; the caller then lets a model do it, as it always did."""
    if read_only_only and not is_read_only(call.tool, mcp_list or [], mcp_tools):
        return "", NOT_READ_ONLY.format(tool=call.tool)
    answer = mcp_tools.call_tool(call.tool, call.arguments)
    if answer.get("is_error"):
        return "", str(answer.get("error") or "")
    return str(answer.get("result") or ""), ""


def has_contract_shape(text: str) -> bool:
    """Whether an answer already starts with the `key: value` lines of the tool contract, so no model has to clean it."""
    first = text.lstrip().split("\n", 1)[0]
    return bool(_CONTRACT_LINE.match(first))
