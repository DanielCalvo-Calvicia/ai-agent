import time

import anyio
from typing import Callable, Dict, List, Optional, Tuple

from application.dtos.outbound.tools import ToolDefinition
from infrastructure.outbound.mcp.connection.call_result import error_types
from infrastructure.outbound.mcp.connection.client_manager import MCPClientManager
from infrastructure.outbound.mcp.config.loader import SUPPORTED_TYPES
from infrastructure.outbound.mcp.connection.limits import FAILED_LISTING_TTL_SECONDS, LIST_TIMEOUT_SECONDS
from infrastructure.outbound.mcp.server import McpServer
from shared_logging import get_logger

logger = get_logger(__name__)


class ListingRecentlyFailed(Exception):
    """The listing of this server failed less than FAILED_LISTING_TTL_SECONDS ago: it is not tried again yet."""


class MCPToolCatalog:
    """
    Knows which tools each MCP server offers and which server owns a tool.
    Only `sse` and `streamable_http` servers are supported (SUPPORTED_TYPES); others and unreachable ones offer no tools.
    A server file with `allowed_tools` offers only those tools; the rest are hidden (and logged as a warning).
    """

    def __init__(self, client_manager: MCPClientManager, clock: Callable[[], float] = time.monotonic):
        self.client_manager = client_manager
        self._clock = clock
        self._failed_until: Dict[str, float] = {}
        self._tools_by_server: Dict[str, List[ToolDefinition]] = {}
        self._server_of_tool: Dict[str, str] = {}

    # -- what the callers use --------------------------------------------------------------------------------------------

    def list_tools(self, server_name: str) -> List[ToolDefinition]:
        """Synchronous. Call it from a worker thread (anyio.run cannot start inside a running event loop)."""
        try:
            return anyio.run(self.list_tools_async, server_name)
        except ListingRecentlyFailed:
            return []
        except Exception as error:
            logger.warning("Could not list MCP tools", server_name=server_name, error_type=error_types(error))
            return []

    def refresh_tools(self, server_name: str) -> List[ToolDefinition]:
        """Forgets what is known about the server (tools and a recent failure) and lists it again, over the network.
        What the optional availability check uses."""
        self._failed_until.pop(server_name, None)
        for tool in self._tools_by_server.pop(server_name, []):
            self._server_of_tool.pop(tool.name, None)
        return self.list_tools(server_name)

    async def list_tools_async(self, server_name: str) -> List[ToolDefinition]:
        if server_name in self._tools_by_server:
            return self._tools_by_server[server_name]

        server = McpServer.find(self.client_manager.configs, server_name)
        if server is None:
            raise ValueError(f"No configuration found for MCP server: {server_name}")
        if server.type not in SUPPORTED_TYPES:
            logger.warning("MCP server protocol is not supported, skipping", server_name=server_name, server_type=server.type)
            return []
        if self._clock() < self._failed_until.get(server_name, 0):
            raise ListingRecentlyFailed(server_name)

        listed = await self._fetch(server_name)
        tools = [_definition_of(tool) for tool in listed if _is_allowed(server_name, tool.name, server.allowed_tools)]
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
            except ListingRecentlyFailed:
                continue
            except Exception as error:
                logger.warning("Error scanning MCP server", server_name=server_name, error_type=error_types(error))
                continue
            if tool_name in self._server_of_tool:
                return self._server_of_tool[tool_name]

        return None

    # -- the listing itself ----------------------------------------------------------------------------------------------

    async def _fetch(self, server_name: str) -> list:
        """The tools the server lists, as the MCP client gives them. A failure starts the quiet time of FAILED_LISTING_TTL_SECONDS."""
        try:
            with anyio.fail_after(LIST_TIMEOUT_SECONDS):
                async with self.client_manager.session_scope(server_name) as session:
                    response = await session.list_tools()
        except Exception:
            self._failed_until[server_name] = self._clock() + FAILED_LISTING_TTL_SECONDS
            raise
        self._failed_until.pop(server_name, None)
        return list(response.tools)


def _definition_of(tool) -> ToolDefinition:
    return ToolDefinition(
        name=tool.name,
        description=tool.description or "",
        parameters=tool.inputSchema or {"type": "object", "properties": {}},
        read_only=_read_only(tool),
    )


def _read_only(tool) -> bool:
    """Whether the server marks the tool as read-only (`annotations.readOnlyHint` is true). The MCP specification calls annotations hints,
    so this is only as good as the server: ai-agent trusts the servers of its own `mcps/` files, and a tool with no hint is not read-only."""
    annotations = getattr(tool, "annotations", None)
    return getattr(annotations, "readOnlyHint", None) is True


def _is_allowed(server_name: str, tool_name: str, allowed: Optional[Tuple[str, ...]]) -> bool:
    """A server file without `allowed_tools` offers every tool; with it, only those (the others are hidden and logged)."""
    if allowed is None or tool_name in allowed:
        return True
    logger.warning("MCP tool is not in allowed_tools, hiding it", server_name=server_name, tool_name=tool_name)
    return False
