# pyright: reportOptionalMemberAccess=false, reportArgumentType=false
"""T-08.3 (ADR-019): a tool call whose tool and parameters are in the plan is made by code; no model rewrites the answer.

A fake port and a scripted LLM: no real call. The operator (phase 5) and the data engineer (phase 6) are only the fallback.
"""
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.ports.outbound.mcp_ports import McpToolsPort
from application.support.tools.scoped_tools import ScopedTools
from domain.value_objects.tools.tool_scope import ToolScope
from application.runtime.flow.pipeline import Pipeline
from application.runtime.step.metrics import SessionMetrics
from application.support.tools.direct_call import DirectCall, call_directly, direct_call_of, has_contract_shape
from domain.entities.llm_response.action import create_action
from flow_trace import FULL_FLOW
from test_flow_golden import PM, ScriptedLLM, _action, _plan

PHASE5 = "phase5_single_action_response_format"
PHASE6 = "phase6_single_action_response_format"
CONTEXT = {"server_id": "any_server", "tool_name": "any_tool", "parameters": {"customer_no": "C-1"}}
TABLE = "status: ok\nreturned: 1\ncomplete: yes\n\nNo.|Status\nSO-1|Open"
MCP_LIST = [{"name": "any_server", "type": "streamable_http", "config": {"type": "streamable_http", "url": "http://placeholder.invalid"}}]


def tool_action(action_id="1", dependencies=None, parameters=None):
    action = {**_action(action_id, "mcp_tool_call"), "mcp_context": {**CONTEXT, "parameters": parameters or CONTEXT["parameters"]}}
    if dependencies:
        action["dependencies"] = dependencies
    return action


class FakeTools(McpToolsPort):
    """Calls a tool the way the adapter does: `{"result": text, "is_error": False}` or `{"error": text, "is_error": True}`."""

    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    def list_tools(self, server_name):
        return []

    def call_tool(self, tool_name, arguments, scope=None):
        self.calls.append((tool_name, dict(arguments)))
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


class CannotCall(McpToolsPort):
    def list_tools(self, server_name):
        return []


def operator_says(text):
    def answer(payload):
        return {"actions": [{**tool_action(), "output": text}]}
    return answer


def run(plan, tools, extra=None):
    llm = ScriptedLLM(overrides={PM: plan, **(extra or {})})
    Pipeline(llm, MCP_LIST, SessionMetrics(), tools, flow=FULL_FLOW).run("the orders of C-1")
    return llm


def count(llm, fmt):
    return sum(1 for call in llm.calls if call["format"] == fmt)


def writer_input(llm):
    return next(c["user_message"] for c in llm.calls if c["format"].startswith("draft_writer"))


# ---------------------------------------------------------------- what an action says

def an_action(**changes):
    values = dict(id_value="1", description_value="read", action_type_value="mcp_tool_call", mcp_context_server_id="s",
                  mcp_context_tool_name="t", mcp_context_parameters={"a": 1})
    return create_action(**{**values, **changes})


def test_an_independent_tool_action_with_a_complete_context_is_a_direct_call():
    assert direct_call_of(an_action()) == DirectCall("t", {"a": 1})


@pytest.mark.parametrize("changes", [
    {"dependencies_list": ["2"]},                                    # it needs the result of another action
    {"action_type_value": "generation"},                              # not a tool call
    {"mcp_context_parameters": {}},                                   # no parameters: the context is not built
    {"mcp_context_tool_name": None},
])
def test_anything_else_is_left_to_the_model(changes):
    assert direct_call_of(an_action(**changes)) is None


def test_an_action_with_subactions_is_left_to_the_model():
    parent = an_action()
    parent.subactions = {"1.1": an_action(id_value="1.1")}

    assert direct_call_of(parent) is None


# ---------------------------------------------------------------- the call

def test_the_answer_of_the_tool_is_the_output_untouched_and_an_error_is_the_error():
    assert call_directly(DirectCall("t", {"a": 1}), FakeTools([{"result": TABLE, "is_error": False}])) == (TABLE, "")
    assert call_directly(DirectCall("t", {"a": 1}), FakeTools([{"error": "error (not_found): nothing", "is_error": True}])) \
        == ("", "error (not_found): nothing")


def test_a_port_that_cannot_call_a_tool_says_so_and_the_caller_lets_a_model_do_it():
    with pytest.raises(NotImplementedError):
        call_directly(DirectCall("t", {"a": 1}), CannotCall())


@pytest.mark.parametrize("text,clean", [
    ("status: ok\nreturned: 1", True), ("returned: 2\ntotal: 2", True), ("coverage: the orders\n\nNo.|S", True), ("  \nstatus: ok", True),
    ('{"data": {"rows": []}}', False), ("No.|Status\nSO-1|Open", False), ("HTTP/1.1 200 OK", False), ("", False),
])
def test_an_answer_with_the_lines_of_the_contract_is_already_clean(text, clean):
    assert has_contract_shape(text) is clean


def test_the_scope_of_a_step_goes_with_the_call():
    seen = []

    class Inner(FakeTools):
        def call_tool(self, tool_name, arguments, scope=None):
            seen.append(scope)
            return {"result": "ok", "is_error": False}

    scope = ToolScope.of({"servers": ["any_server"]})

    ScopedTools(Inner([]), scope).call_tool("any_tool", {"a": 1})

    assert seen == [scope]


# ---------------------------------------------------------------- through the executor

def test_an_independent_tool_action_runs_with_no_operator_and_no_data_engineer():
    tools = FakeTools([{"result": TABLE, "is_error": False}])

    llm = run(_plan(tool_action()), tools)

    assert tools.calls == [("any_tool", {"customer_no": "C-1"})]
    assert count(llm, PHASE5) == 0 and count(llm, PHASE6) == 0
    assert "SO-1|Open" in writer_input(llm)                           # the rows reach the writer as the tool wrote them


def test_an_answer_that_is_not_clean_still_goes_through_the_data_engineer():
    tools = FakeTools([{"result": '{"data": {"rows": ["SO-1"]}}', "is_error": False}])

    llm = run(_plan(tool_action()), tools, extra={PHASE6: lambda payload: {"actions": [{**tool_action(), "output": "cleaned rows SO-1"}]}})

    assert count(llm, PHASE5) == 0 and count(llm, PHASE6) == 1
    assert "cleaned rows SO-1" in writer_input(llm)


def test_a_tool_error_is_the_error_of_the_action_and_no_model_is_asked_again():
    tools = FakeTools([{"error": "error (not_found): no such customer", "is_error": True}])

    llm = run(_plan(tool_action()), tools)

    assert len(tools.calls) == 1 and count(llm, PHASE5) == 0 and count(llm, PHASE6) == 0
    assert "error (not_found): no such customer" in writer_input(llm)


def test_a_dependent_action_still_goes_to_the_operator_model():
    tools = FakeTools([{"result": TABLE, "is_error": False}])
    plan = _plan(tool_action("1"), tool_action("2", dependencies=["1"]))

    llm = run(plan, tools, extra={PHASE5: lambda payload: {"actions": [{**tool_action("2", dependencies=["1"]), "output": "status: ok\nsecond, by the operator"}]}})

    assert len(tools.calls) == 1                                       # action 1 by code; action 2 left to the model
    assert count(llm, PHASE5) == 1
    assert "second, by the operator" in writer_input(llm)


def test_a_port_that_cannot_call_a_tool_leaves_the_action_to_the_operator_model_as_before():
    llm = run(_plan(tool_action()), CannotCall(), extra={PHASE5: operator_says("status: ok\nby the operator")})

    assert count(llm, PHASE5) == 1
    assert "by the operator" in writer_input(llm)


def test_without_a_tools_port_the_operator_runs_as_before():
    llm = run(_plan(tool_action()), None, extra={PHASE5: operator_says("status: ok\nby the operator")})

    assert count(llm, PHASE5) == 1


def test_the_cap_of_tool_calls_per_message_counts_the_direct_calls(monkeypatch):
    monkeypatch.setenv("AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE", "1")
    tools = FakeTools([{"result": TABLE, "is_error": False}])

    llm = run(_plan(tool_action("1"), tool_action("2", parameters={"customer_no": "C-2"})), tools)

    assert len(tools.calls) == 1
    assert "only the first 1 could be done" in writer_input(llm)
