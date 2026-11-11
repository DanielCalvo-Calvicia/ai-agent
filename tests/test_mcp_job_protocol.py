"""The job protocol seam (T-07.3, ADR-018): `none` by default, a name the registry knows, settings that must make sense."""

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from infrastructure.outbound.mcp import job_protocol
from infrastructure.outbound.mcp.config import load_supported_mcp_configs
from infrastructure.outbound.mcp.job_protocol import (
    DONE,
    NO_JOBS,
    JobProtocol,
    JobRef,
    NoJobs,
    get_protocol,
    job_protocol_problem,
    known_protocols,
)
from infrastructure.outbound.mcp.tool_executor import MCPToolExecutor

ANSWER = "returned: 1\njob_id: abc\nstatus: running\n\nNo.|Status\nPV-1|Open"   # looks like a job, and the server has none


class _Fake(JobProtocol):
    name = "fake"

    def detect(self, answer: str) -> List[JobRef]:
        return []

    def read_arguments(self, job: JobRef) -> Dict[str, Any]:
        return {"job_id": job.job_id}

    def state(self, answer: str) -> str:
        return DONE

    def merge(self, answer: str, results: List[str]) -> str:
        return answer

    def cancel_arguments(self, job: JobRef) -> Dict[str, Any]:
        return {"job_id": job.job_id}


@pytest.fixture
def fake_protocol(monkeypatch):
    monkeypatch.setitem(job_protocol._PROTOCOLS, "fake", _Fake())


def test_the_registry_knows_none_and_refuses_any_other_name():
    assert NO_JOBS in known_protocols()
    assert isinstance(get_protocol(NO_JOBS), NoJobs)
    for name in ("nope", "", None, 3, ["none"]):
        with pytest.raises(ValueError):
            get_protocol(name)


def test_none_finds_no_job_in_any_answer_and_says_every_answer_is_done():
    protocol = get_protocol(NO_JOBS)

    assert protocol.detect(ANSWER) == [] and protocol.detect("") == []
    assert protocol.state(ANSWER) == DONE and protocol.merge(ANSWER, ["x"]) == ANSWER
    assert protocol.read_arguments(JobRef("abc")) == {} and protocol.cancel_arguments(JobRef("abc", 5)) == {}


def test_a_server_without_the_field_is_none_and_needs_nothing_else():
    assert job_protocol_problem({"url": "http://placeholder"}) is None
    assert job_protocol_problem({"job_protocol": "none", "job_read_tool": 5}) is None   # a `none` server ignores the tools


@pytest.mark.parametrize("config,reason", [
    ({"job_protocol": "nope"}, "unknown job protocol"),
    ({"job_protocol": 3}, "unknown job protocol"),
    ({"job_protocol": "fake"}, "needs a job_read_tool"),
    ({"job_protocol": "fake", "job_read_tool": ""}, "needs a job_read_tool"),
    ({"job_protocol": "fake", "job_read_tool": "read", "job_cancel_tool": 7}, "must be a tool name"),
    ({"job_protocol": "fake", "job_read_tool": "read", "allowed_tools": ["other"]}, "not in allowed_tools"),
    ({"job_protocol": "fake", "job_read_tool": "read", "job_cancel_tool": "cancel", "allowed_tools": ["read"]}, "not in allowed_tools"),
    ({"job_protocol": "fake", "job_read_tool": "read", "job_recall_tools": "ship"}, "must be a list of tool names"),
    ({"job_protocol": "fake", "job_read_tool": "read", "job_recall_tools": ["ok", 3]}, "must be a list of tool names"),
    ({"job_protocol": "fake", "job_read_tool": "read", "job_recall_tools": ["ship"], "allowed_tools": ["read"]}, "job_recall_tools 'ship' is not in allowed_tools"),
])
def test_job_settings_that_cannot_work_are_named(fake_protocol, config, reason):
    assert reason in job_protocol_problem(config)


def test_job_settings_that_work_have_no_problem(fake_protocol):
    assert job_protocol_problem({"job_protocol": "fake", "job_read_tool": "read"}) is None
    assert job_protocol_problem({"job_protocol": "fake", "job_read_tool": "read", "job_recall_tools": ["ship"], "allowed_tools": ["read", "ship"]}) is None
    assert job_protocol_problem({"job_protocol": "fake", "job_read_tool": "read", "job_cancel_tool": "cancel",
                                 "allowed_tools": ["read", "cancel", "x"]}) is None


def test_the_loader_keeps_a_server_without_the_field_and_skips_one_with_bad_job_settings(tmp_path, fake_protocol):
    servers = {
        "plain": {"type": "streamable_http", "url": "http://placeholder"},
        "good": {"type": "streamable_http", "url": "http://placeholder", "job_protocol": "fake", "job_read_tool": "read"},
        "unknown": {"type": "streamable_http", "url": "http://placeholder", "job_protocol": "nope"},
        "no_tool": {"type": "streamable_http", "url": "http://placeholder", "job_protocol": "fake"},
    }
    for name, config in servers.items():
        (tmp_path / f"{name}.json").write_text(json.dumps({name: config}), encoding="utf-8")

    assert sorted(s["name"] for s in load_supported_mcp_configs(str(tmp_path))) == ["good", "plain"]


def test_the_shipped_server_files_have_valid_job_settings():
    assert all(job_protocol_problem(s["config"]) is None for s in load_supported_mcp_configs())


class _Manager:
    """A client manager whose tool answers `text`; its server file has the settings given."""

    def __init__(self, text, server_config=None):
        self.configs = {"local": {"name": "local", "type": "streamable_http",
                                  "config": {"url": "http://placeholder.invalid/mcp", **(server_config or {})}}}
        self.text = text
        self.calls = []

    @asynccontextmanager
    async def session_scope(self, server_name):
        async def call_tool(name, arguments=None):
            self.calls.append(name)
            return SimpleNamespace(isError=False, content=[SimpleNamespace(text=self.text)])
        yield SimpleNamespace(call_tool=call_tool)


def _execute(manager):
    executor = MCPToolExecutor(manager)
    executor.catalog._server_of_tool["any_tool"] = "local"
    return executor.execute("any_tool", {})


def test_with_none_the_executor_returns_exactly_what_the_server_answered():
    for config in (None, {"job_protocol": "none"}):
        manager = _Manager(ANSWER, config)

        answer = _execute(manager)

        assert answer == {"result": ANSWER, "is_error": False}
        assert manager.calls == ["any_tool"]            # nothing was followed


def test_an_unknown_name_that_got_past_the_loader_is_treated_as_none():
    manager = _Manager(ANSWER, {"job_protocol": "nope"})

    assert _execute(manager) == {"result": ANSWER, "is_error": False}
