# pyright: reportOptionalMemberAccess=false
"""AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE: a confused plan cannot make many tool calls for one message."""
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.orchestration.engine.pipeline import Pipeline
from application.orchestration.flows.action_executor import MCP_CAP_REACHED
from application.orchestration.support import failure
from application.orchestration.support.failure import max_mcp_calls
from application.orchestration.support.metrics import SessionMetrics
from flow_trace import FULL_FLOW
from test_flow_golden import PM, ScriptedLLM, _action, _no_result, _plan

PHASE5 = "phase5_single_action_response_format"
VARIABLE = "AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE"
MCP_LIST = [{"name": "aws_microservice", "type": "sse", "config": {"type": "sse", "url": "http://x"}}]


class _Warnings:
    def __init__(self):
        self.records = []

    def warning(self, message, **fields):
        self.records.append((message, fields))


def run(*actions, phase5=None):
    """Runs a plan; returns (the LLM, the actions as they ended)."""
    overrides = {PM: _plan(*actions)}
    if phase5:
        overrides[PHASE5] = phase5
    llm = ScriptedLLM(overrides=overrides)
    result = Pipeline(llm, MCP_LIST, SessionMetrics(), flow=FULL_FLOW).run("do it")
    return llm, result.state.actions


def tool_calls(llm):
    return sum(1 for call in llm.calls if call["format"] == PHASE5)


def four():
    return [_action(str(i), "mcp_tool_call") for i in range(1, 5)]


def error_of(action):
    return action.error.get_value() if action.error else None


# ---------------------------------------------------------------- the value

def test_the_default_is_5(monkeypatch):
    monkeypatch.delenv(VARIABLE, raising=False)
    assert max_mcp_calls() == 5


@pytest.mark.parametrize("value,expected", [("2", 2), ("0", 0), (" 7 ", 7)])
def test_a_whole_number_is_used_and_zero_means_no_limit(monkeypatch, value, expected):
    monkeypatch.setenv(VARIABLE, value)
    assert max_mcp_calls() == expected


@pytest.mark.parametrize("value", ["abc", "-1", "2.5", "1e3"])
def test_an_invalid_value_uses_5_with_a_warning_never_0(monkeypatch, value):
    log = _Warnings()
    monkeypatch.setattr(failure, "logger", log)
    monkeypatch.setenv(VARIABLE, value)

    assert max_mcp_calls() == 5
    assert [fields["variable"] for _, fields in log.records] == [VARIABLE]


# ---------------------------------------------------------------- the cap

def test_with_the_cap_at_2_and_4_tool_actions_2_run_2_are_skipped_and_the_writer_is_told(monkeypatch):
    monkeypatch.setenv(VARIABLE, "2")

    llm, actions = run(*four())

    assert tool_calls(llm) == 2
    assert [error_of(a) for a in actions[:2]] == [None, None]
    assert [error_of(a) for a in actions[2:]] == [MCP_CAP_REACHED.format(cap=2)] * 2
    assert "only the first 2 could be done" in MCP_CAP_REACHED.format(cap=2)
    # a later step of the flow (the writer) is given those errors, the way it is given any failed action
    writer_calls = [c for c in llm.calls if "only the first 2 could be done" in c["user_message"]]
    assert writer_calls and all(not c["format"].startswith("phase5") for c in writer_calls)


def test_with_0_every_action_runs(monkeypatch):
    monkeypatch.setenv(VARIABLE, "0")

    llm, actions = run(*four())

    assert tool_calls(llm) == 4 and all(error_of(a) is None for a in actions)


def test_by_default_the_sixth_tool_action_is_the_first_one_not_run(monkeypatch):
    monkeypatch.delenv(VARIABLE, raising=False)

    llm, actions = run(*[_action(str(i), "mcp_tool_call") for i in range(1, 7)])

    assert tool_calls(llm) == 5
    assert error_of(actions[5]) == MCP_CAP_REACHED.format(cap=5) and error_of(actions[4]) is None


def test_the_retries_of_one_action_do_not_count(monkeypatch):
    monkeypatch.setenv(VARIABLE, "1")
    monkeypatch.setenv("AI_AGENT_MAX_ATTEMPTS", "3")

    llm, actions = run(_action("1", "mcp_tool_call"), _action("2", "mcp_tool_call"), phase5=_no_result)

    assert tool_calls(llm) == 3                       # the one action, asked 3 times
    assert error_of(actions[0]) == "tool unavailable"   # it ran and failed
    assert error_of(actions[1]) == MCP_CAP_REACHED.format(cap=1)


def test_the_dependants_of_a_skipped_action_are_skipped_as_for_any_failed_action(monkeypatch):
    monkeypatch.setenv(VARIABLE, "1")

    _, actions = run(_action("1", "mcp_tool_call"), _action("2", "mcp_tool_call"), _action("3", dependencies=["2"]))

    assert error_of(actions[1]) == MCP_CAP_REACHED.format(cap=1)
    assert "skipped" in error_of(actions[2])


def test_actions_that_are_not_tool_calls_are_not_counted(monkeypatch):
    monkeypatch.setenv(VARIABLE, "1")

    llm, actions = run(_action("1"), _action("2"), _action("3", "mcp_tool_call"))

    assert tool_calls(llm) == 1 and error_of(actions[2]) is None
