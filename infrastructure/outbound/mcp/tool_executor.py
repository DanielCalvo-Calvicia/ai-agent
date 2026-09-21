import anyio
from typing import Any, Dict, List, Optional

from application.outbound.ports.mcp_ports import McpToolsPort
from domain.value_objects.tool import ToolDefinition
from infrastructure.outbound.mcp.client_manager import MCPClientManager
from infrastructure.outbound.mcp.tool_catalog import SERVER_TIMEOUT_SECONDS, MCPToolCatalog


class MCPToolExecutor(McpToolsPort):
    """
    What the LLM adapter uses for MCP: `list_tools` to offer the tools of a server and
    `execute` to run one. Synchronous, so call it from a worker thread.
    """

    def __init__(self, client_manager: MCPClientManager, catalog: Optional[MCPToolCatalog] = None):
        self.client_manager = client_manager
        self.catalog = catalog or MCPToolCatalog(client_manager)

    def list_tools(self, server_name: str) -> List[ToolDefinition]:
        return self.catalog.list_tools(server_name)

    def execute(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return anyio.run(self._execute_async, tool_name, args)

    async def _execute_async(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        server_name = await self.catalog.server_of(tool_name)
        if not server_name:
            return {"error": f"Tool '{tool_name}' not found on any registered MCP server.", "is_error": True}

        try:
            with anyio.fail_after(SERVER_TIMEOUT_SECONDS):
                async with self.client_manager.session_scope(server_name) as session:
                    result = await session.call_tool(tool_name, arguments=args)

            if result.isError:
                return {"error": result.content, "is_error": True}

            return {"result": "\n".join(_content_as_text(item) for item in result.content), "is_error": False}
        except Exception as e:
            return {"error": f"MCP execution error: {str(e)}", "is_error": True}


def _content_as_text(item: Any) -> str:
    return item.text if hasattr(item, 'text') and 'text' in item.__dict__ else str(item)
