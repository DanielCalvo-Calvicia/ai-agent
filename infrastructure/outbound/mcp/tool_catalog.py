import math
import os
import time

import anyio
from typing import Callable, Dict, List, Optional

from domain.value_objects.llm_request.tool import ToolDefinition
from infrastructure.outbound.mcp.client_manager import MCPClientManager
from infrastructure.outbound.mcp.config import SUPPORTED_TYPES
from shared_logging import get_logger

logger = get_logger(__name__)

# Seconds to wait for one MCP server to list its tools before giving up on it.
LIST_TIMEOUT_SECONDS = 10

# A listing that failed is not tried again for this long, so a server that is down costs one LIST_TIMEOUT_SECONDS wait
# per minute (a successful listing is kept for the life of the process).
FAILED_LISTING_TTL_SECONDS = 60

# Seconds one tool call may take (connect, initialize and the call). A slow query makes the server wait up to
# 20 s (dynamics_microservice MCP_JOB_WAIT) before it answers `running`, so this stays above that.
CALL_TIMEOUT_VARIABLE = "AI_AGENT_MCP_CALL_TIMEOUT_SECONDS"
DEFAULT_CALL_TIMEOUT_SECONDS = 30


def call_timeout_seconds() -> float:
    """The limit of one tool call: the variable, or the default when it is not a positive number."""
    raw = os.environ.get(CALL_TIMEOUT_VARIABLE, "").strip()
    if not raw:
        return DEFAULT_CALL_TIMEOUT_SECONDS
    try:
        value = float(raw)
        if value > 0 and math.isfinite(value):
            return value
    except ValueError:
        pass
    logger.warning("Invalid MCP call timeout, using the default", variable=CALL_TIMEOUT_VARIABLE, default=DEFAULT_CALL_TIMEOUT_SECONDS)
    return DEFAULT_CALL_TIMEOUT_SECONDS


class ListingRecentlyFailed(Exception):
    """The listing of this server failed less than FAILED_LISTING_TTL_SECONDS ago: it is not tried again yet."""


def error_types(error: BaseException) -> str:
    """The class names of an error (inside the exception groups the MCP clients raise).
    Used instead of its text or traceback, which can hold the address of the server."""
    if isinstance(error, BaseExceptionGroup):
        return ",".join(sorted({error_types(inner) for inner in error.exceptions}))
    return type(error).__name__


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

        config = self.client_manager.configs.get(server_name)
        if config is None:
            raise ValueError(f"No configuration found for MCP server: {server_name}")

        if config.get("type", "sse") not in SUPPORTED_TYPES:
            logger.warning(
                "MCP server protocol is not supported, skipping",
                server_name=server_name,
                server_type=config.get("type"),
            )
            return []

        if self._clock() < self._failed_until.get(server_name, 0):
            raise ListingRecentlyFailed(server_name)

        try:
            with anyio.fail_after(LIST_TIMEOUT_SECONDS):
                async with self.client_manager.session_scope(server_name) as session:
                    response = await session.list_tools()
        except Exception:
            self._failed_until[server_name] = self._clock() + FAILED_LISTING_TTL_SECONDS
            raise
        self._failed_until.pop(server_name, None)

        allowed = (config.get("config") or {}).get("allowed_tools")
        tools = [
            ToolDefinition(
                name=t.name,
                description=t.description or "",
                parameters=t.inputSchema or {"type": "object", "properties": {}},
            )
            for t in response.tools
            if _is_allowed(server_name, t.name, allowed)
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
            except ListingRecentlyFailed:
                continue
            except Exception as error:
                logger.warning("Error scanning MCP server", server_name=server_name, error_type=error_types(error))
                continue
            if tool_name in self._server_of_tool:
                return self._server_of_tool[tool_name]

        return None


def _is_allowed(server_name: str, tool_name: str, allowed: Optional[List[str]]) -> bool:
    """A server file without `allowed_tools` offers every tool; with it, only those (the others are hidden and logged)."""
    if allowed is None or tool_name in allowed:
        return True
    logger.warning("MCP tool is not in allowed_tools, hiding it", server_name=server_name, tool_name=tool_name)
    return False
