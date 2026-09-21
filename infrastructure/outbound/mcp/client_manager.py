from contextlib import asynccontextmanager
from typing import Any, Dict, List

from mcp import ClientSession
from mcp.client.sse import sse_client
from shared_logging import inject_headers


class MCPClientManager:
    """Opens a session to a configured MCP server. Only SSE servers (config["config"]["url"])."""

    def __init__(self, configs: List[Dict[str, Any]]):
        self.configs = {cfg["name"]: cfg for cfg in configs}

    @asynccontextmanager
    async def session_scope(self, server_name: str):
        """Async context manager for a server session."""
        if server_name not in self.configs:
            raise ValueError(f"No configuration found for MCP server: {server_name}")

        url = self.configs[server_name].get("config", {}).get("url")

        # propagate the trace context to the MCP server (W3C traceparent)
        async with sse_client(url, headers=dict(inject_headers())) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                yield session
