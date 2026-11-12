from typing import Any, Dict, List, Optional

from application.ports.outbound.mcp_ports import McpToolsPort
from domain.value_objects.llm_request.tool import ToolDefinition
from domain.value_objects.tools.tool_scope import ToolScope


class ScopedTools(McpToolsPort):
    """The tools port a step sees: only the tools its scope allows."""

    def __init__(self, inner: McpToolsPort, scope: ToolScope) -> None:
        self.inner = inner
        self.scope = scope

    def list_tools(self, server_name: str) -> List[ToolDefinition]:
        if not self.scope.may_use(server_name):
            return []
        return [tool for tool in self.inner.list_tools(server_name) if self.scope.allows(server_name, tool.name)]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any], scope: Optional[ToolScope] = None) -> Dict[str, Any]:
        """The call goes through the scope of the step: a tool it does not allow is refused and no server is called."""
        return self.inner.call_tool(tool_name, arguments, scope=self.scope)


def scoped(mcp_list: list, mcp_tools: Optional[McpToolsPort], scope: ToolScope):
    """
    The servers and the tools port a step is built with. An unlimited scope gives back what it was given. Each server of a
    limited scope carries the scope under `scope`, so the adapter exposes and runs only the tools it allows.
    """
    if scope.unlimited:
        return mcp_list, mcp_tools
    servers = [{**server, "scope": scope} for server in mcp_list if scope.may_use(server["name"])]
    return servers, (ScopedTools(mcp_tools, scope) if mcp_tools else None)
