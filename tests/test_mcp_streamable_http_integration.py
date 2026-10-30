"""
Runs a real MCP server (FastMCP over Streamable HTTP, stateless, JSON answers: how dynamics_microservice serves it)
on a free local port and checks that MCPToolExecutor lists and calls its tools. Nothing leaves the machine.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from types import SimpleNamespace
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

from application.orchestration.support.mcp_servers import describe_servers, server_names
from application.outbound.ports.mcp_ports import remaining_tool_wait, tool_wait_budget, watch_tool_failures
from infrastructure.outbound.mcp.client_manager import MCPClientManager
from infrastructure.outbound.mcp.tool_catalog import LIST_TIMEOUT_SECONDS, call_timeout_seconds
from infrastructure.outbound.mcp import tool_executor
from infrastructure.outbound.mcp.tool_executor import MCPToolExecutor

SECRET_ARGUMENT = "CUSTOMER-PLACEHOLDER-123"
CALLS = {}   # how many times the server ran each tool (the server runs in this process)


def _count(tool: str) -> int:
    CALLS[tool] = CALLS.get(tool, 0) + 1
    return CALLS[tool]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def http_server():
    port = _free_port()
    mcp = FastMCP("test-server", stateless_http=True, json_response=True)

    @mcp.tool()
    def echo(text: str) -> str:
        """Returns the text it receives."""
        return f"echo:{text}"

    @mcp.tool()
    def fail(text: str) -> str:
        """Always fails, like a tool that answers `error (not_found)`."""
        _count("fail")
        raise ValueError("error (not_found): nothing here")

    @mcp.tool()
    def flaky(always: bool) -> str:
        """Answers `error (retry_later)`: always, or only the first time."""
        if _count("flaky") == 1 or always:
            raise ValueError("error (retry_later): busy")
        return "flaky:ok"

    @mcp.tool()
    async def slow(seconds: float) -> str:
        """Answers after the seconds it is given."""
        _count("slow")
        await asyncio.sleep(seconds)
        return f"slow:{seconds}"

    server = uvicorn.Server(uvicorn.Config(mcp.streamable_http_app(), host="127.0.0.1", port=port, log_config=None))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started, "the test MCP server did not start"

    yield f"http://127.0.0.1:{port}/mcp"

    server.should_exit = True
    thread.join(timeout=5)


def _manager(url: str) -> MCPClientManager:
    return MCPClientManager([{"name": "local", "type": "streamable_http", "config": {"type": "streamable_http", "url": url}}])


def _executor(url: str) -> MCPToolExecutor:
    return MCPToolExecutor(_manager(url))


def test_lists_the_tools_of_the_server(http_server):
    tools = _executor(http_server).list_tools("local")
    assert sorted(t.name for t in tools) == ["echo", "fail", "flaky", "slow"]
    assert "text" in next(t for t in tools if t.name == "echo").parameters["properties"]


def test_executes_a_tool(http_server):
    assert _executor(http_server).execute("echo", {"text": "hi"}) == {"result": "echo:hi", "is_error": False}


def test_a_tool_error_comes_back_as_is_error(http_server):
    result = _executor(http_server).execute("fail", {"text": "x"})
    assert result["is_error"] is True


def test_unknown_tool_is_an_error(http_server):
    assert _executor(http_server).execute("nope", {})["is_error"] is True


def test_a_down_server_is_an_error_not_an_exception():
    result = _executor(f"http://127.0.0.1:{_free_port()}/mcp").execute("echo", {"text": "x"})
    assert result["is_error"] is True


def test_no_log_line_holds_an_argument_or_an_answer(http_server, caplog):
    caplog.set_level(logging.DEBUG)
    executor = _executor(http_server)
    executor.list_tools("local")
    executor.execute("echo", {"text": SECRET_ARGUMENT})
    executor.execute("fail", {"text": SECRET_ARGUMENT})
    # the client libraries log at DEBUG too; our own code must never put a value in a line
    ours = [r for r in caplog.records if r.name.startswith("infrastructure.")]
    assert not any(SECRET_ARGUMENT in r.getMessage() or f"echo:{SECRET_ARGUMENT}" in r.getMessage() for r in ours)


def test_a_server_without_url_names_the_server_not_the_url():
    manager = MCPClientManager([{"name": "no_url", "type": "streamable_http", "config": {"type": "streamable_http", "url": ""}}])

    async def open_session():
        async with manager.session_scope("no_url"):
            pass

    with pytest.raises(ValueError, match="no_url"):
        asyncio.run(open_session())


def test_an_unsupported_type_cannot_open_a_session():
    manager = MCPClientManager([{"name": "odd", "type": "websocket", "config": {"url": "http://127.0.0.1:1/x"}}])

    async def open_session():
        async with manager.session_scope("odd"):
            pass

    with pytest.raises(ValueError, match="Unsupported"):
        asyncio.run(open_session())


@pytest.fixture(autouse=True)
def _fresh_counts(monkeypatch):
    CALLS.clear()
    monkeypatch.delenv("AI_AGENT_MCP_CALL_TIMEOUT_SECONDS", raising=False)


def test_the_call_limit_is_30_seconds_by_default_and_listing_stays_at_10():
    assert call_timeout_seconds() == 30
    assert LIST_TIMEOUT_SECONDS == 10


@pytest.mark.parametrize("value", ["0", "-5", "abc", "nan", "inf"])
def test_an_invalid_call_limit_falls_back_to_the_default(monkeypatch, value):
    monkeypatch.setenv("AI_AGENT_MCP_CALL_TIMEOUT_SECONDS", value)
    assert call_timeout_seconds() == 30


def test_the_call_limit_can_be_set(monkeypatch):
    monkeypatch.setenv("AI_AGENT_MCP_CALL_TIMEOUT_SECONDS", "45.5")
    assert call_timeout_seconds() == 45.5


def test_a_slow_answer_inside_the_limit_succeeds(http_server, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MCP_CALL_TIMEOUT_SECONDS", "5")
    assert _executor(http_server).execute("slow", {"seconds": 1.5}) == {"result": "slow:1.5", "is_error": False}


def test_a_call_that_never_answers_fails_at_the_limit_with_a_timeout_message_and_is_not_retried(http_server, monkeypatch):
    monkeypatch.setenv("AI_AGENT_MCP_CALL_TIMEOUT_SECONDS", "1")
    result = _executor(http_server).execute("slow", {"seconds": 3})
    assert result["is_error"] is True and "timed out" in result["error"]
    assert CALLS.get("slow", 0) <= 1   # never run twice (under load the 1 s limit can pass before the server starts the tool)


def test_retry_later_is_retried_once_and_can_succeed(http_server):
    assert _executor(http_server).execute("flaky", {"always": False}) == {"result": "flaky:ok", "is_error": False}
    assert CALLS["flaky"] == 2


def test_retry_later_that_keeps_failing_is_tried_twice_and_no_more(http_server):
    result = _executor(http_server).execute("flaky", {"always": True})
    assert result["is_error"] is True and "retry_later" in result["error"]
    assert CALLS["flaky"] == 2


def test_a_tool_error_that_is_not_retry_later_is_not_retried(http_server):
    result = _executor(http_server).execute("fail", {"text": "x"})
    assert result["is_error"] is True and "not_found" in result["error"]
    assert CALLS["fail"] == 1


class _CountingManager(MCPClientManager):
    """Counts the sessions it is asked to open."""

    opened = 0

    def session_scope(self, server_name):
        self.opened += 1
        return super().session_scope(server_name)


def test_a_transport_error_is_retried_once_and_the_answer_does_not_hold_the_address():
    url = f"http://127.0.0.1:{_free_port()}/mcp"
    manager = _CountingManager([{"name": "local", "type": "streamable_http", "config": {"url": url}}])
    executor = MCPToolExecutor(manager)
    executor.catalog._server_of_tool["echo"] = "local"   # known from an earlier listing, so only the call is tried

    result = executor.execute("echo", {"text": "x"})

    assert result["is_error"] is True and "transport" in result["error"] and url not in result["error"]
    assert manager.opened == 2


def _final_after(executor, tool, args):
    with watch_tool_failures() as failures:
        executor.execute(tool, args)
    return failures.final


def test_a_failure_for_good_is_reported_to_the_step_that_is_watching(http_server, monkeypatch):
    executor = _executor(http_server)
    assert _final_after(executor, "fail", {"text": "x"}) is True            # not_found
    assert _final_after(executor, "flaky", {"always": True}) is True        # retry_later, retry spent
    assert _final_after(executor, "nope", {}) is True                       # no server offers it
    monkeypatch.setenv("AI_AGENT_MCP_CALL_TIMEOUT_SECONDS", "1")
    assert _final_after(executor, "slow", {"seconds": 3}) is True           # timeout


def test_a_success_is_not_reported_even_after_a_retry(http_server):
    executor = _executor(http_server)
    assert _final_after(executor, "echo", {"text": "x"}) is False
    CALLS.clear()
    assert _final_after(executor, "flaky", {"always": False}) is False      # retry_later, then ok


def test_a_dead_server_is_hidden_from_the_planner_and_listed_once_per_minute():
    url = f"http://127.0.0.1:{_free_port()}/mcp"
    manager = _CountingManager([{"name": "local", "type": "streamable_http", "config": {"url": url}}])
    executor = MCPToolExecutor(manager)
    configs = [{"name": "local", "type": "streamable_http", "config": {"url": url}}]

    assert describe_servers(configs, executor) == [] and server_names(configs, executor) == []
    assert describe_servers(configs, executor) == []
    assert manager.opened == 1


def test_a_live_server_is_shown_to_the_planner_with_its_tools(http_server):
    configs = [{"name": "local", "type": "streamable_http", "config": {"url": http_server}}]

    assert server_names(configs, _executor(http_server)) == ["local"]
    [server] = describe_servers(configs, _executor(http_server))
    assert sorted(t["name"] for t in server["tools"]) == ["echo", "fail", "flaky", "slow"]


class _Recorder:
    """Stands in for a module logger and keeps what was logged."""

    def __init__(self):
        self.records = []

    def info(self, message, **fields):
        self.records.append(("info", message, fields))

    def warning(self, message, **fields):
        self.records.append(("warning", message, fields))


def _calls(executor, tool, args):
    """The tool calls a watching step collects while one call is made."""
    with watch_tool_failures() as watching:
        executor.execute(tool, args)
    return watching.calls


def test_a_call_is_recorded_with_its_tool_its_outcome_and_a_duration(http_server):
    [call] = _calls(_executor(http_server), "echo", {"text": SECRET_ARGUMENT})

    assert (call.tool, call.outcome, call.attempts) == ("echo", "ok", 1)
    assert call.duration_ms >= 0 and call.ended_ns >= call.started_ns > 0


def test_the_outcome_kind_of_every_way_a_call_can_end(http_server, monkeypatch):
    executor = _executor(http_server)
    assert _calls(executor, "fail", {"text": "x"})[0].outcome == "not_found"            # error (not_found)
    [exhausted] = _calls(executor, "flaky", {"always": True})
    assert (exhausted.outcome, exhausted.attempts) == ("retry_later", 2)                 # retried once, still failing
    CALLS.clear()
    [recovered] = _calls(executor, "flaky", {"always": False})
    assert (recovered.outcome, recovered.attempts) == ("ok", 2)                          # retried once, then ok
    assert _calls(executor, "nope", {})[0].outcome == "not_found"                        # no server offers it
    assert _calls(executor, "nope", {})[0].attempts == 0
    monkeypatch.setenv("AI_AGENT_MCP_CALL_TIMEOUT_SECONDS", "1")
    assert _calls(executor, "slow", {"seconds": 3})[0].outcome == "timeout"


def test_a_transport_error_is_recorded_after_its_retry():
    url = f"http://127.0.0.1:{_free_port()}/mcp"
    executor = MCPToolExecutor(MCPClientManager([{"name": "local", "type": "streamable_http", "config": {"url": url}}]))
    executor.catalog._server_of_tool["echo"] = "local"

    [call] = _calls(executor, "echo", {"text": "x"})

    assert (call.outcome, call.attempts) == ("transport", 2)


class _ErrorManager:
    """A client manager whose tool always fails with the text given."""

    def __init__(self, text):
        self.configs = {"local": {"name": "local", "type": "streamable_http", "config": {"url": "http://placeholder.invalid/mcp"}}}
        self.text = text

    @asynccontextmanager
    async def session_scope(self, server_name):
        async def call_tool(name, arguments=None):
            return SimpleNamespace(isError=True, content=[SimpleNamespace(text=self.text)])
        yield SimpleNamespace(call_tool=call_tool)


@pytest.mark.parametrize("text,outcome", [
    ("error (input): bad customer code", "input"),
    ("error (source_problem): the source failed", "source_problem"),
    ("error (internal): boom", "internal"),
    ("something broke, with no kind", "internal"),
    ("error (surprise): a kind nobody knows", "internal"),
    ("error (ok): a tool cannot claim our own outcomes", "internal"),
    ("error (timeout): nor this one", "internal"),
])
def test_the_kind_of_a_tool_error_is_read_from_its_text_and_anything_else_is_internal(text, outcome):
    executor = MCPToolExecutor(_ErrorManager(text))
    executor.catalog._server_of_tool["any_tool"] = "local"

    [call] = _calls(executor, "any_tool", {})

    assert (call.outcome, call.attempts) == (outcome, 1)


def test_the_log_line_of_a_call_holds_the_tool_the_outcome_and_the_duration_and_no_value(http_server, monkeypatch):
    log = _Recorder()
    monkeypatch.setattr(tool_executor, "logger", log)
    executor = _executor(http_server)

    executor.execute("echo", {"text": SECRET_ARGUMENT})
    executor.execute("fail", {"text": SECRET_ARGUMENT})

    lines = [fields for _, message, fields in log.records if message == "MCP tool call"]
    assert [(f["tool_name"], f["outcome"]) for f in lines] == [("echo", "ok"), ("fail", "not_found")]
    assert all(set(f) == {"tool_name", "outcome", "duration_ms", "attempts"} for f in lines)
    assert SECRET_ARGUMENT not in repr(log.records)


def test_without_a_watching_step_a_call_still_works_and_is_logged(http_server, monkeypatch):
    log = _Recorder()
    monkeypatch.setattr(tool_executor, "logger", log)

    assert _executor(http_server).execute("echo", {"text": "x"})["is_error"] is False
    assert [m for _, m, _ in log.records] == ["MCP tool call"]


def test_without_a_budget_there_is_no_limit_on_the_total_wait():
    assert remaining_tool_wait() is None


def test_a_call_gets_only_what_is_left_of_the_wait_of_the_message(http_server):
    executor = _executor(http_server)

    with tool_wait_budget(10.0) as budget:
        budget.spend(8.5)                                                              # earlier calls used most of it
        assert 1.4 < budget.remaining() < 1.6
        second = executor.execute("slow", {"seconds": 5.0})                            # gets what is left, not 30 s
        assert second["is_error"] is True and "timed out" in second["error"]
        assert budget.remaining() == 0
        third = _calls(executor, "slow", {"seconds": 0.1})                             # nothing is left: not even tried
        assert (third[0].outcome, third[0].attempts) == ("timeout", 0)


def test_a_call_with_no_wait_left_says_so_and_the_server_is_not_asked(http_server):
    executor = _executor(http_server)

    with tool_wait_budget(1.0) as budget:
        budget.spend(1.0)
        answer = executor.execute("echo", {"text": "x"})

    assert answer["is_error"] is True and "No wait is left" in answer["error"]
    assert CALLS.get("echo", 0) == 0


def test_the_wait_is_a_sum_over_calls_so_fast_calls_do_not_exhaust_it(http_server):
    executor = _executor(http_server)

    with tool_wait_budget(60.0) as budget:
        for _ in range(3):
            assert executor.execute("echo", {"text": "x"})["is_error"] is False

    assert budget.remaining() > 50
