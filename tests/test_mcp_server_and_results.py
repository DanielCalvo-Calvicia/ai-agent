"""The small parts of infrastructure/outbound/mcp/ that the bigger tests only touch: the view of a server entry, how a call
result is told apart, and the one-way imports of the jobs package."""

import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from infrastructure.outbound.mcp.connection.call_result import (
    content_as_text, error_kind, error_types, failure, is_timeout, success,
)
from infrastructure.outbound.mcp.server import McpServer


def _entry(**config):
    return {"name": "orders", "type": "streamable_http", "config": config}


def test_a_server_entry_is_read_in_one_place():
    server = McpServer.find({"orders": _entry(url="http://placeholder", allowed_tools=["a", "b"], job_protocol="dynamics_v1",
                                              job_read_tool="read", job_cancel_tool="cancel", job_recall_tools=["a"])}, "orders")
    assert (server.name, server.type, server.url) == ("orders", "streamable_http", "http://placeholder")
    assert server.allowed_tools == ("a", "b") and server.job_recall_tools == ("a",)
    assert (server.job_protocol, server.job_read_tool, server.job_cancel_tool) == ("dynamics_v1", "read", "cancel")


def test_a_server_entry_with_nothing_set_has_no_limits_and_no_jobs():
    server = McpServer.from_entry("orders", {"name": "orders", "config": {}})
    assert server.type == "sse" and server.url is None          # the type a manager assumes when the entry has none
    assert server.allowed_tools is None and server.job_protocol == "none" and server.job_recall_tools == ()


def test_an_empty_allowed_tools_list_is_kept_as_empty_not_as_no_limit():
    assert McpServer.find({"orders": _entry(allowed_tools=[])}, "orders").allowed_tools == ()


@pytest.mark.parametrize("configs", [None, {}, {"other": _entry()}])
def test_a_server_that_is_not_there_is_none(configs):
    assert McpServer.find(configs, "orders") is None


def test_an_answer_is_a_result_or_an_error():
    assert success("x") == {"result": "x", "is_error": False}
    assert failure("x") == {"error": "x", "is_error": True}


def test_the_kind_of_a_tool_error_is_read_from_its_text():
    assert error_kind("error (retry_later): busy") == "retry_later"
    assert error_kind("something else") is None


def test_a_timeout_is_known_alone_or_inside_a_group_and_a_mixed_group_is_not_one():
    assert is_timeout(TimeoutError()) and is_timeout(httpx.ReadTimeout("x"))
    assert is_timeout(BaseExceptionGroup("g", [TimeoutError(), httpx.ConnectTimeout("x")]))
    assert not is_timeout(BaseExceptionGroup("g", [TimeoutError(), OSError()]))


def test_an_error_is_told_by_its_class_names_never_by_its_text():
    assert error_types(ValueError("http://secret.example/mcp")) == "ValueError"
    assert error_types(BaseExceptionGroup("g", [OSError("x"), ValueError("y"), OSError("z")])) == "OSError,ValueError"


def test_the_text_of_a_content_item_is_its_text_or_its_str():
    class Text:
        def __init__(self):
            self.text = "hello"

    assert content_as_text(Text()) == "hello"
    assert content_as_text(5) == "5"


@pytest.mark.parametrize("first", [
    "infrastructure.outbound.mcp.jobs.protocols.dynamics_v1",
    "infrastructure.outbound.mcp.jobs.protocols.dynamics_pending",
    "infrastructure.outbound.mcp.jobs.settings",
    "infrastructure.outbound.mcp.config.loader",
])
def test_every_job_module_imports_first_with_no_lazy_import(first):
    """The protocols import the interface, the registry imports the protocols and nothing goes the other way."""
    code = f"import {first}; from infrastructure.outbound.mcp.jobs.registry import known_protocols; print(known_protocols())"
    root = str(Path(__file__).resolve().parent.parent)
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [root, os.environ.get("PYTHONPATH", "")]))}
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60, cwd=root, env=env)
    assert done.returncode == 0, done.stderr
    assert "dynamics_v1" in done.stdout and "none" in done.stdout
