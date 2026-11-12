# ===============================================
#  TOOL RESOLVER
#  Turns the tools of a payload into ToolSpec objects. No SDK is imported here:
#  vercel/tool_adapter.py wraps the specs into ai_sdk Tools.
# ===============================================

from typing import Any, List, Optional

from infrastructure.outbound.llm.shared.providers.config import LLMConfig
from infrastructure.outbound.llm.shared.tools.handlers import handler_for
from infrastructure.outbound.llm.shared.tools.spec import ToolSpec
from shared_logging import get_logger

logger = get_logger(__name__)


def resolve_tool_specs(config: LLMConfig, tools: Optional[list]) -> List[Any]:
    """
    An entry can be:
      - an object that already has a handler (an SDK tool): returned as is;
      - an MCP server descriptor (dict with "name" and "config"): expanded into the
        tools that server offers, through config.tool_executor. Without an executor
        the server is skipped. A descriptor with a `scope` (domain/value_objects/tools/tool_scope.py, T-05.13) offers
        only the tools the scope allows, and those tools run only through it;
      - a domain ToolDefinition: turned into a ToolSpec, executed through config.tool_executor
        (a mock answer when there is no executor).
    """
    resolved: List[Any] = []

    for tool in tools or []:
        if hasattr(tool, "handler"):
            resolved.append(tool)
        elif isinstance(tool, dict):
            resolved.extend(_specs_of_server(config, tool))
        else:
            resolved.append(_spec_of(config, tool))

    return resolved


def _specs_of_server(config: LLMConfig, server: dict) -> List[ToolSpec]:
    if not config.tool_executor:
        logger.warning("No MCP tool executor configured, skipping MCP server", server_name=server.get("name"))
        return []

    scope = server.get("scope")
    return [_spec_of(config, definition, scope) for definition in config.tool_executor.list_tools(server["name"])
            if scope is None or scope.allows(server["name"], definition.name)]


def _spec_of(config: LLMConfig, definition, scope=None) -> ToolSpec:
    return ToolSpec(
        name=definition.name,
        description=definition.description,
        parameters=definition.parameters,
        handler=handler_for(config, definition.name, scope),
    )
