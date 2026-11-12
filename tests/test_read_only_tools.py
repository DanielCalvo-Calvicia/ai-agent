# pyright: reportOptionalMemberAccess=false, reportArgumentType=false
"""T-08.4 (ADR-019): the fast path has no safety gate step, so it runs only tools their server marks as read-only (`readOnlyHint`).

The check is at run time: `assemble()` works from files only and the annotation is on the live server.
"""
import os
import sys

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.ports.outbound.mcp_ports import McpToolsPort
from application.support.tools.scoped_tools import ScopedTools
from domain.value_objects.tools.tool_scope import ToolScope
from application.support.tools.direct_call import NOT_READ_ONLY, DirectCall, call_directly, is_read_only
from application.support.tools.mcp_servers import describe_servers, server_names
from domain.value_objects.llm_request.tool import ToolDefinition
from infrastructure.outbound.mcp.connection.client_manager import MCPClientManager
from infrastructure.outbound.mcp.execution.tool_executor import MCPToolExecutor
from test_mcp_dynamics_flow import _serve

SERVER = "any_server"
MCP_LIST = [{"name": SERVER, "type": "streamable_http", "config": {"type": "streamable_http", "url": "http://placeholder.invalid"}}]


@pytest.fixture(scope="module")
def server_url():
    mcp = FastMCP("fake", stateless_http=True, json_response=True)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def read_things(code: str) -> str:
        """Reads."""
        return f"status: ok\nreturned: 1\n\nNo.|S\n{code}|Open"

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
    def delete_things(code: str) -> str:
        """Changes data."""
        return "status: ok"

    @mcp.tool()
    def says_nothing(code: str) -> str:
        """No annotation at all."""
        return "status: ok"

    server, thread, port = _serve(mcp.streamable_http_app())
    yield f"http://127.0.0.1:{port}/mcp"
    server.should_exit = True
    thread.join(timeout=5)


def executor_for(url):
    return MCPToolExecutor(MCPClientManager([{"name": SERVER, "type": "streamable_http", "config": {"type": "streamable_http", "url": url}}]))


# ---------------------------------------------------------------- the catalog reads the hint

def test_a_tool_is_read_only_only_if_its_server_says_so(server_url):
    tools = {t.name: t.read_only for t in executor_for(server_url).list_tools(SERVER)}

    assert tools == {"read_things": True, "delete_things": False, "says_nothing": False}


def test_a_definition_is_not_read_only_by_default_and_the_openai_form_does_not_change():
    tool = ToolDefinition(name="t", description="d", parameters={"type": "object"})

    assert tool.read_only is False
    assert tool.to_openai_dict() == {"type": "function", "function": {"name": "t", "description": "d", "parameters": {"type": "object"}}}


# ---------------------------------------------------------------- what the selector is shown

def test_only_the_read_only_tools_are_shown_when_the_fast_path_asks(server_url):
    executor = executor_for(server_url)

    every = describe_servers(MCP_LIST, executor)
    read_only = describe_servers(MCP_LIST, executor, read_only_only=True)

    assert [t["name"] for t in every[0]["tools"]] == ["read_things", "delete_things", "says_nothing"]
    assert [t["name"] for t in read_only[0]["tools"]] == ["read_things"]
    assert server_names(MCP_LIST, executor) == [SERVER] and server_names(MCP_LIST, executor, read_only_only=True) == [SERVER]


def test_a_server_with_no_read_only_tool_is_left_out_for_the_fast_path():
    class OnlyWriting(McpToolsPort):
        def list_tools(self, server_name):
            return [ToolDefinition("delete_things", "d", {"type": "object"})]

    assert describe_servers(MCP_LIST, OnlyWriting(), read_only_only=True) == []
    assert server_names(MCP_LIST, OnlyWriting(), read_only_only=True) == [] and server_names(MCP_LIST, OnlyWriting()) == [SERVER]


def test_the_scope_of_the_step_still_applies_before_the_read_only_filter(server_url):
    scoped = ScopedTools(executor_for(server_url), ToolScope.of({"tools": ["read_things"]}))

    assert [t["name"] for t in describe_servers(MCP_LIST, scoped)[0]["tools"]] == ["read_things"]


# ---------------------------------------------------------------- the call

class Recording(McpToolsPort):
    def __init__(self, read_only):
        self.read_only, self.called = read_only, []

    def list_tools(self, server_name):
        return [ToolDefinition("any_tool", "d", {"type": "object"}, read_only=self.read_only)]

    def call_tool(self, tool_name, arguments, scope=None):
        self.called.append(tool_name)
        return {"result": "status: ok", "is_error": False}


def test_a_tool_that_is_not_read_only_is_refused_and_no_server_is_called():
    port = Recording(read_only=False)

    output, error = call_directly(DirectCall("any_tool", {"a": 1}), port, MCP_LIST, read_only_only=True)

    assert output == "" and error == NOT_READ_ONLY.format(tool="any_tool") and port.called == []


def test_a_read_only_tool_is_called_by_the_fast_path():
    port = Recording(read_only=True)

    assert call_directly(DirectCall("any_tool", {"a": 1}), port, MCP_LIST, read_only_only=True) == ("status: ok", "")
    assert port.called == ["any_tool"]


def test_without_the_servers_nothing_can_be_proved_read_only_so_the_call_is_refused():
    port = Recording(read_only=True)

    output, error = call_directly(DirectCall("any_tool", {"a": 1}), port, None, read_only_only=True)

    assert output == "" and error and port.called == []
    assert is_read_only("any_tool", [], port) is False


def test_a_tool_no_server_offers_is_not_read_only():
    assert is_read_only("unknown_tool", MCP_LIST, Recording(read_only=True)) is False


def test_the_existing_callers_are_not_affected_by_the_check():
    port = Recording(read_only=False)

    assert call_directly(DirectCall("any_tool", {"a": 1}), port) == ("status: ok", "")      # the executor of `special` and `dynamics`
    assert port.called == ["any_tool"]


def test_the_real_catalog_and_the_real_call_agree(server_url):
    executor = executor_for(server_url)
    mcp_list = [{"name": SERVER, "type": "streamable_http", "config": {}}]

    ok = call_directly(DirectCall("read_things", {"code": "C-1"}), executor, mcp_list, read_only_only=True)
    refused = call_directly(DirectCall("delete_things", {"code": "C-1"}), executor, mcp_list, read_only_only=True)
    undeclared = call_directly(DirectCall("says_nothing", {"code": "C-1"}), executor, mcp_list, read_only_only=True)

    assert ok[0].startswith("status: ok") and ok[1] == ""
    assert refused == ("", NOT_READ_ONLY.format(tool="delete_things")) and undeclared == ("", NOT_READ_ONLY.format(tool="says_nothing"))


def test_the_optional_check_names_the_tools_that_are_not_marked_read_only_in_its_one_line(server_url, monkeypatch):
    from infrastructure.outbound.mcp.catalog import availability
    from infrastructure.outbound.mcp.catalog.tool_catalog import MCPToolCatalog

    lines = []

    class Log:
        def info(self, message, **fields):
            lines.append((message, fields))

        warning = info

    monkeypatch.setattr(availability, "logger", Log())
    monkeypatch.setenv(availability.check_variable(SERVER), "1")
    executor = executor_for(server_url)

    availability.McpAvailabilityCheck(MCPToolCatalog(executor.client_manager), [SERVER]).run()

    [fields] = [f for m, f in lines if m == "MCP server checked, it is reachable"]       # still one line for an up server
    assert fields == {"server_name": SERVER, "tools": 3, "not_read_only": ["delete_things", "says_nothing"]}
