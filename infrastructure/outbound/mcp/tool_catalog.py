import anyio
from typing import Dict, List, Optional

from domain.value_objects.llm_request.tool import ToolDefinition
from infrastructure.outbound.mcp.client_manager import MCPClientManager
from shared_logging import get_logger

logger = get_logger(__name__)

# Seconds to wait for one MCP server before giving up on it.
SERVER_TIMEOUT_SECONDS = 10


class MCPToolCatalog:
    """
    Knows which tools each MCP server offers and which server owns a tool.
    Only `sse` servers are supported; others and unreachable ones offer no tools.
    """

    def __init__(self, client_manager: MCPClientManager):
        self.client_manager = client_manager
        self._tools_by_server: Dict[str, List[ToolDefinition]] = {}
        self._server_of_tool: Dict[str, str] = {}

    def list_tools(self, server_name: str) -> List[ToolDefinition]:
        """Synchronous. Call it from a worker thread (anyio.run cannot start inside a running event loop)."""
        try:
            return anyio.run(self.list_tools_async, server_name)
        except Exception:
            logger.warning("Could not list MCP tools", server_name=server_name, exc_info=True)
            return []

    async def list_tools_async(self, server_name: str) -> List[ToolDefinition]:
        if server_name in self._tools_by_server:
            return self._tools_by_server[server_name]

        config = self.client_manager.configs.get(server_name)
        if config is None:
            raise ValueError(f"No configuration found for MCP server: {server_name}")

        if config.get("type", "sse") != "sse":
            logger.warning(
                "MCP server protocol is not supported, skipping",
                server_name=server_name,
                server_type=config.get("type"),
            )
            return []

        with anyio.fail_after(SERVER_TIMEOUT_SECONDS):
            async with self.client_manager.session_scope(server_name) as session:
                response = await session.list_tools()

        tools = [
            ToolDefinition(
                name=t.name,
                description=t.description or "",
                parameters=t.inputSchema or {"type": "object", "properties": {}},
            )
            for t in response.tools
        ]
        self._tools_by_server[server_name] = tools
        for tool in tools:
            self._server_of_tool[tool.name] = server_name
        return tools

    async def server_of(self, tool_name: str) -> Optional[str]:
        """The server that offers the tool, looking at every configured server if needed."""
        if tool_name in self._server_of_tool:
            return self._server_of_tool[tool_name]

        for server_name in self.client_manager.configs:
            try:
                await self.list_tools_async(server_name)
            except Exception:
                logger.warning("Error scanning MCP server", server_name=server_name, exc_info=True)
                continue
            if tool_name in self._server_of_tool:
                return self._server_of_tool[tool_name]

        return None
