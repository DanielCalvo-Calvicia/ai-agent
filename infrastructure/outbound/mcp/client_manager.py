import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from shared_logging import inject_headers

# The libraries under the MCP client log the address of the server (httpx, httpcore) and, at DEBUG, the whole message
# sent, which holds the arguments of a tool call (mcp). Keep them quiet whatever LOG_LEVEL says: no URL, no argument and
# no answer may reach a log.
_CHATTY_LIBRARIES = ("httpx", "httpcore", "mcp.client")


def quiet_client_libraries() -> None:
    for name in _CHATTY_LIBRARIES:
        logging.getLogger(name).setLevel(logging.WARNING)


quiet_client_libraries()

class MCPClientManager:
    """Opens a session to a configured MCP server (config["config"]["url"]): `sse` or `streamable_http`."""

    def __init__(self, configs: List[Dict[str, Any]]):
        self.configs = {cfg["name"]: cfg for cfg in configs}

    @asynccontextmanager
    async def session_scope(self, server_name: str):
        """Async context manager for a server session."""
        if server_name not in self.configs:
            raise ValueError(f"No configuration found for MCP server: {server_name}")

        config = self.configs[server_name]
        url = config.get("config", {}).get("url")
        if not url:
            raise ValueError(f"MCP server '{server_name}' has no url configured")

        # propagate the trace context to the MCP server (W3C traceparent)
        headers = dict(inject_headers())

        async with self._streams(config.get("type", "sse"), url, headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    @asynccontextmanager
    async def _streams(self, server_type: str, url: str, headers: Dict[str, str]):
        """The (read, write) streams of the transport of `server_type`."""
        if server_type == "streamable_http":
            # a third element (session id getter) is not needed: the server is stateless and each call opens its own session
            async with streamablehttp_client(url, headers=headers) as (read, write, _get_session_id):
                yield read, write
        elif server_type == "sse":
            async with sse_client(url, headers=headers) as (read, write):
                yield read, write
        else:
            raise ValueError(f"Unsupported MCP server type: {server_type}")
