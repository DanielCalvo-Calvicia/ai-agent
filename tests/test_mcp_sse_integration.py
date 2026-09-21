"""
Runs a real MCP server (FastMCP over SSE) on a free local port and checks that
MCPToolExecutor discovers its tools and executes them. Nothing leaves the machine.
"""
import os
import socket
import sys
import threading
import time

import pytest
import uvicorn
from mcp.server.fastmcp import FastMCP

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from infrastructure.outbound.llm.config import VercelAIConfig
from infrastructure.outbound.llm.tools import resolve_tools
from infrastructure.outbound.mcp.client_manager import MCPClientManager
from infrastructure.outbound.mcp.tool_executor import MCPToolExecutor


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def sse_server():
    port = _free_port()
    mcp = FastMCP("test-server")

    @mcp.tool()
    def echo(text: str) -> str:
        """Returns the text it receives."""
        return f"echo:{text}"

    server = uvicorn.Server(uvicorn.Config(mcp.sse_app(), host="127.0.0.1", port=port, log_config=None))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started, "the test MCP server did not start"

    yield f"http://127.0.0.1:{port}/sse"

    server.should_exit = True
    thread.join(timeout=5)


def _executor(url: str) -> MCPToolExecutor:
    configs = [{"name": "local", "type": "sse", "config": {"type": "sse", "url": url}}]
    return MCPToolExecutor(MCPClientManager(configs))


def test_lists_the_tools_of_the_server(sse_server):
    tools = _executor(sse_server).list_tools("local")
    assert [t.name for t in tools] == ["echo"]
    assert "text" in tools[0].parameters["properties"]


def test_executes_a_tool(sse_server):
    result = _executor(sse_server).execute("echo", {"text": "hi"})
    assert result == {"result": "echo:hi", "is_error": False}


def test_finds_the_server_of_a_tool_without_listing_first(sse_server):
    assert _executor(sse_server).execute("echo", {"text": "x"})["is_error"] is False


def test_unknown_tool_is_an_error(sse_server):
    assert _executor(sse_server).execute("nope", {})["is_error"] is True


def test_phase5_style_server_descriptor_becomes_callable_tools(sse_server):
    executor = _executor(sse_server)
    descriptor = {"name": "local", "type": "sse", "config": {"url": sse_server}}
    tools = resolve_tools(VercelAIConfig(tool_executor=executor), [descriptor])
    assert [t.name for t in tools] == ["echo"]
    assert tools[0].handler(text="yo") == {"result": "echo:yo", "is_error": False}
