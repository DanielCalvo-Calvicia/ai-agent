# pyright: reportOptionalMemberAccess=false
"""A server that is down is hidden from the planner and costs one wait per minute; the optional check only logs."""
import os
import sys
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.orchestration.support.mcp_servers import describe_servers, server_names
from application.outbound.ports.mcp_ports import McpToolsPort
from application.service.session_service import SessionService
from domain.value_objects.llm_request.tool import ToolDefinition
from infrastructure.inbound.http.fastapi import SessionFastAPI
from infrastructure.outbound.mcp import availability, tool_catalog
from infrastructure.outbound.mcp.availability import McpAvailabilityCheck, check_variable
from infrastructure.outbound.mcp.tool_catalog import FAILED_LISTING_TTL_SECONDS, MCPToolCatalog
from test_session_fastapi import MockLLMAdapter

URL = "http://placeholder.invalid:9/mcp"


class _Warnings:
    """Stands in for a module logger and keeps what was logged (level, message, fields)."""

    def __init__(self):
        self.records = []

    def warning(self, message, **fields):
        self.records.append(("warning", message, fields))

    def info(self, message, **fields):
        self.records.append(("info", message, fields))


class _Port(McpToolsPort):
    """A tools port with a fixed answer per server."""

    def __init__(self, tools_by_server):
        self.tools_by_server = tools_by_server

    def list_tools(self, server_name):
        return self.tools_by_server.get(server_name, [])


def _tool(name):
    return ToolDefinition(name=name, description="d", parameters={"type": "object", "properties": {}})


class _Manager:
    """A client manager whose listing fails while `down` is set; it counts the sessions it is asked to open."""

    def __init__(self, names=("srv",), down=True):
        self.configs = {n: {"name": n, "type": "streamable_http", "config": {"url": URL}} for n in names}
        self.down = down
        self.opened = 0

    @asynccontextmanager
    async def session_scope(self, server_name):
        self.opened += 1
        if self.down:
            raise ConnectionError("connection refused by " + URL)

        async def list_tools():
            return SimpleNamespace(tools=[SimpleNamespace(name="ok_tool", description="", inputSchema=None)])
        yield SimpleNamespace(list_tools=list_tools)


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


# ---------------------------------------------------------------- hidden when down

MCP_LIST = [{"name": "up", "type": "sse", "config": {}}, {"name": "down", "type": "sse", "config": {}}]


def test_a_server_that_offers_no_tools_is_left_out_for_the_planner():
    port = _Port({"up": [_tool("a")]})

    assert server_names(MCP_LIST, port) == ["up"]
    assert [s["name"] for s in describe_servers(MCP_LIST, port)] == ["up"]


def test_without_a_tools_port_every_configured_server_is_still_named():
    assert server_names(MCP_LIST) == ["up", "down"]
    assert [s["name"] for s in describe_servers(MCP_LIST, None)] == ["up", "down"]


def test_when_every_server_is_down_none_is_offered():
    port = _Port({})

    assert server_names(MCP_LIST, port) == [] and describe_servers(MCP_LIST, port) == []


# ---------------------------------------------------------------- the cache of a failed listing

def test_a_failed_listing_is_not_tried_again_for_60_seconds_then_it_is():
    manager, clock = _Manager(), _Clock()
    catalog = MCPToolCatalog(manager, clock=clock)

    assert catalog.list_tools("srv") == [] and catalog.list_tools("srv") == []
    assert manager.opened == 1
    clock.now += FAILED_LISTING_TTL_SECONDS - 1
    assert catalog.list_tools("srv") == [] and manager.opened == 1
    clock.now += 2
    catalog.list_tools("srv")
    assert manager.opened == 2


def test_a_server_that_comes_back_is_picked_up_after_the_60_seconds():
    manager, clock = _Manager(), _Clock()
    catalog = MCPToolCatalog(manager, clock=clock)
    catalog.list_tools("srv")
    manager.down = False
    assert catalog.list_tools("srv") == []                      # still inside the minute
    clock.now += FAILED_LISTING_TTL_SECONDS + 1

    assert [t.name for t in catalog.list_tools("srv")] == ["ok_tool"]
    assert catalog.list_tools("srv")[0].name == "ok_tool" and manager.opened == 2   # and a success is kept


def test_a_failure_is_logged_with_the_server_and_the_error_type_never_the_address(monkeypatch):
    log = _Warnings()
    monkeypatch.setattr(tool_catalog, "logger", log)

    MCPToolCatalog(_Manager(), clock=_Clock()).list_tools("srv")

    [(_, message, fields)] = log.records
    assert fields == {"server_name": "srv", "error_type": "ConnectionError"}
    assert URL not in repr(log.records)


def test_a_failure_inside_the_wait_is_not_logged_again(monkeypatch):
    log = _Warnings()
    monkeypatch.setattr(tool_catalog, "logger", log)
    catalog = MCPToolCatalog(_Manager(), clock=_Clock())

    catalog.list_tools("srv")
    catalog.list_tools("srv")

    assert len(log.records) == 1


def test_refresh_lists_again_even_inside_the_wait():
    manager = _Manager()
    catalog = MCPToolCatalog(manager, clock=_Clock())
    catalog.list_tools("srv")
    manager.down = False

    assert [t.name for t in catalog.refresh_tools("srv")] == ["ok_tool"]
    assert manager.opened == 2


# ---------------------------------------------------------------- the optional check

def test_the_variable_is_the_server_name_in_upper_case():
    assert check_variable("dynamics_microservice") == "AI_AGENT_CHECK_MCP_DYNAMICS_MICROSERVICE"
    assert check_variable("my-server.v2") == "AI_AGENT_CHECK_MCP_MY_SERVER_V2"


@pytest.mark.parametrize("value", [None, "0", "", "yes"])
def test_without_the_variable_set_to_1_nothing_is_checked(monkeypatch, value):
    monkeypatch.delenv("AI_AGENT_CHECK_MCP_SRV", raising=False)
    if value is not None:
        monkeypatch.setenv("AI_AGENT_CHECK_MCP_SRV", value)
    manager = _Manager()

    assert McpAvailabilityCheck(MCPToolCatalog(manager), ["srv"]).run() == []
    assert manager.opened == 0


def test_with_the_variable_a_server_that_is_down_is_logged_as_a_warning_naming_it(monkeypatch):
    monkeypatch.setenv("AI_AGENT_CHECK_MCP_SRV", "1")
    log = _Warnings()
    monkeypatch.setattr(availability, "logger", log)

    assert McpAvailabilityCheck(MCPToolCatalog(_Manager(), clock=_Clock()), ["srv"]).run() == ["srv"]

    [(level, _, fields)] = log.records
    assert level == "warning" and fields == {"server_name": "srv"}


def test_with_the_variable_a_server_that_is_up_is_not_a_warning(monkeypatch):
    monkeypatch.setenv("AI_AGENT_CHECK_MCP_SRV", "1")
    log = _Warnings()
    monkeypatch.setattr(availability, "logger", log)

    assert McpAvailabilityCheck(MCPToolCatalog(_Manager(down=False)), ["srv"]).run() == []
    assert [level for level, _, _ in log.records] == ["info"]


def test_the_check_looks_at_the_network_every_time_not_at_the_cache(monkeypatch):
    monkeypatch.setenv("AI_AGENT_CHECK_MCP_SRV", "1")
    manager = _Manager()
    check = McpAvailabilityCheck(MCPToolCatalog(manager, clock=_Clock()), ["srv"])

    check.run()
    check.run()

    assert manager.opened == 2


# ---------------------------------------------------------------- /available does not change

def _client(check=None):
    app = FastAPI()
    SessionFastAPI(App=app, SessionPort=SessionService(outbound_port=MockLLMAdapter()), AvailabilityCheck=check)
    return TestClient(app)


def _answer(client):
    body = client.get("/available").json()
    body.pop("timestamp", None)
    return client.get("/available").status_code, body


def test_available_answers_exactly_as_before_whatever_the_check_does():
    calls = []

    def failing_check():
        calls.append(1)
        raise RuntimeError("boom")

    plain = _answer(_client())
    assert _answer(_client(lambda: calls.append(1))) == plain
    assert _answer(_client(failing_check)) == plain
    assert len(calls) == 4              # two calls of /available per answer, the check ran on each


def test_without_a_check_available_runs_none():
    assert _answer(_client())[0] == 200
