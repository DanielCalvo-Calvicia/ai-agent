# ===============================================
#  TOOLS
#  Turns the tools of a payload into ai_sdk Tools.
# ===============================================

from typing import Any, List, Optional

from ai_sdk.tool import Tool

from infrastructure.outbound.llm.config import VercelAIConfig
from shared_logging import get_logger

logger = get_logger(__name__)


def resolve_tools(config: VercelAIConfig, tools: Optional[list]) -> List[Any]:
    """
    An entry can be:
      - an ai_sdk Tool (has a handler): used as is;
      - an MCP server descriptor (dict with "name" and "config"): expanded into the
        tools that server offers, through config.tool_executor. Without an executor
        the server is skipped. A descriptor with a `scope` (application/outbound/ports/mcp_ports.py, T-05.13) offers
        only the tools the scope allows, and those tools run only through it;
      - a domain ToolDefinition: wrapped, executed through config.tool_executor
        (a mock answer when there is no executor).
    """
    resolved: List[Any] = []

    for tool in tools or []:
        if hasattr(tool, "handler"):
            resolved.append(tool)
        elif isinstance(tool, dict):
            resolved.extend(_tools_of_server(config, tool))
        else:
            resolved.append(_wrap(config, tool))

    return resolved


def _tools_of_server(config: VercelAIConfig, server: dict) -> List[Tool]:
    if not config.tool_executor:
        logger.warning("No MCP tool executor configured, skipping MCP server", server_name=server.get("name"))
        return []

    scope = server.get("scope")
    return [_wrap(config, definition, scope) for definition in config.tool_executor.list_tools(server["name"])
            if scope is None or scope.allows(server["name"], definition.name)]


def _wrap(config: VercelAIConfig, definition, scope=None) -> Tool:
    return Tool(
        name=definition.name,
        description=definition.description,
        parameters=definition.parameters,
        handler=_handler_for(config, definition.name, scope),
    )


def _handler_for(config: VercelAIConfig, name: str, scope=None):
    executor = config.tool_executor
    if executor:
        if scope is not None:
            return lambda **kwargs: executor.execute(name, kwargs, scope=scope)
        return lambda **kwargs: executor.execute(name, kwargs)
    return lambda **kwargs: {"status": "success", "tool": name, "args": kwargs}
