# pyright: reportOptionalMemberAccess=false, reportArgumentType=false
"""T-08.5 (ADR-019): the fast flow of the profile `dynamics_fast` with a scripted LLM and a fake tools port.

A tool call and a reply are two model calls and one code step: no triage, no planner, no gate, no operator, no data engineer, no editor.
"""
import os

import pytest

from application.assembly.assemble import assemble
from application.assembly.config_snapshot import build_snapshot
from application.ports.outbound.mcp_ports import McpToolsPort
from application.runtime.profile.runner import ProfileRunner
from application.runtime.step.metrics import SessionMetrics
from domain.value_objects.llm_request.tool import ToolDefinition
from infrastructure.outbound.config.file_source import FileConfigSource
from infrastructure.outbound.llm.shared.schemas.anthropic_schema import anthropic_schema_problems
from infrastructure.outbound.mcp.config.loader import load_tool_snapshot
from test_flow_golden import SCENARIOS, ScriptedLLM, _action, _identification_output, read_inputs, read_response_json
from test_resume import CHECK, Script, _verdict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SELECTOR = "tool_selector_phase50_response_format"
WRITER = "answer_writer_phase51_response_format"
SERVER = "dynamics_microservice"
MCP_LIST = [{"name": SERVER, "type": "streamable_http", "config": {"url": "http://placeholder.invalid"}}]
TABLE = "status: ok\nreturned: 2\ncomplete: yes\n\nNo.|Status\nSO-1|Open\nSO-2|Open"
PROCEED = {"ready_to_execute": True, "status": "proceed", "recommended_action": "", "blocking_reason": "", "requested_user_input": []}
ASKING = {"ready_to_execute": False, "status": "awaiting_user_input", "recommended_action": "ask_user_for_missing_information",
          "blocking_reason": "the customer code is missing", "requested_user_input": ["the customer code"]}


@pytest.fixture(scope="module")
def agent():
    built = assemble(build_snapshot(FileConfigSource(PROJECT_ROOT)), mcp_servers=load_tool_snapshot(),
                     schema_rules={"anthropic": anthropic_schema_problems})
    built.raise_on_errors()
    return built


class Tools(McpToolsPort):
    """Two tools of one server: a read-only one and one that is not. `call_tool` is what the caller uses."""

    def __init__(self, answers=None):
        self.answers, self.calls = list(answers or [{"result": TABLE, "is_error": False}]), []

    def list_tools(self, server_name):
        return [ToolDefinition("read_orders", "Reads the orders of a customer.", {"type": "object"}, read_only=True),
                ToolDefinition("delete_orders", "Deletes the orders of a customer.", {"type": "object"}, read_only=False)]

    def call_tool(self, tool_name, arguments, scope=None):
        self.calls.append((tool_name, dict(arguments)))
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


def tool_action(tool="read_orders", action_id="1", **changes):
    return {**_action(action_id, "mcp_tool_call"), "mcp_context": {"server_id": SERVER, "tool_name": tool, "parameters": {"customer_no": "C-1"}}, **changes}


def selects(*actions, next_step=PROCEED):
    return {"actions": list(actions), "next_step": next_step}


def writes(text="the reply"):
    return {"user_goal": {"summary": "s", "expected_outcome": text}}


def run(agent, selection, tools=None, writer=None, message="the orders of C-1"):
    llm = ScriptedLLM(overrides={SELECTOR: selection, WRITER: writer or writes()})
    values = read_inputs(agent.profile("dynamics_fast"),
                         _identification_output(SCENARIOS["communication_goes_to_the_conversation_flow"]["llm"]["overrides"]), read_response_json)
    runner = ProfileRunner(llm, MCP_LIST, SessionMetrics(), tools if tools is not None else Tools(), agent)
    return runner.run("dynamics_fast", message, inputs=values), llm, runner


def formats(llm):
    return [c["format"] for c in llm.calls]


def writer_input(llm):
    return next(c["user_message"] for c in llm.calls if c["format"] == WRITER)


# ---------------------------------------------------------------- the whole path

def test_one_tool_call_and_a_reply_are_two_model_calls_and_one_code_step(agent):
    tools = Tools()

    result, llm, _ = run(agent, selects(tool_action()), tools)

    assert formats(llm) == [SELECTOR, WRITER]                                  # no triage, planner, gate, operator, engineer or editor
    assert tools.calls == [("read_orders", {"customer_no": "C-1"})]
    assert result.reply == "the reply" and result.paused is None and result.flow == "fast"
    assert "SO-2|Open" in writer_input(llm)                                    # the tool answer reaches the writer untouched


def test_the_selector_is_shown_only_the_read_only_tools_of_the_profile(agent):
    _, llm, _ = run(agent, selects(tool_action()))

    shown = next(c["user_message"] for c in llm.calls if c["format"] == SELECTOR)
    assert "read_orders" in shown and "delete_orders" not in shown
    assert "the orders of C-1" in shown                                        # the user's own words, for the codes


def test_the_flow_and_the_profile_are_the_ones_the_task_names(agent):
    profile = agent.profile("dynamics_fast")

    assert profile.flow_name == "fast" and profile.steps == ["tool_selector", "tool_caller", "answer_writer"]
    assert profile.requires == ["user_goal", "task_category"] and profile.default_return == "text"


# ---------------------------------------------------------------- what is not a tool call

def test_when_no_tool_fits_the_selector_says_what_to_tell_and_no_tool_is_called(agent):
    tools = Tools()
    reply = {**_action("1", "generation"), "description": "Greet the user back, briefly."}

    result, llm, _ = run(agent, selects(reply), tools)

    assert tools.calls == [] and formats(llm) == [SELECTOR, WRITER]
    assert "Greet the user back, briefly." in writer_input(llm)


def test_a_second_tool_call_is_not_made_and_the_writer_is_told_plainly(agent):
    tools = Tools()

    _, llm, _ = run(agent, selects(tool_action(action_id="1"), tool_action(action_id="2")), tools)

    assert len(tools.calls) == 1
    assert "makes one tool call per request" in writer_input(llm)


# ---------------------------------------------------------------- what is refused

def test_a_tool_that_is_not_read_only_is_refused_and_never_called(agent):
    tools = Tools()

    _, llm, _ = run(agent, selects(tool_action("delete_orders")), tools)

    assert tools.calls == []
    assert "not marked read-only" in writer_input(llm)


def test_an_incomplete_call_is_not_made(agent):
    tools = Tools()
    incomplete = tool_action()
    incomplete["mcp_context"]["parameters"] = {}

    _, llm, _ = run(agent, selects(incomplete), tools)

    assert tools.calls == [] and "was not complete" in writer_input(llm)


def test_a_tool_error_reaches_the_writer_and_no_model_is_asked_again(agent):
    tools = Tools([{"error": "error (not_found): no such customer", "is_error": True}])

    _, llm, _ = run(agent, selects(tool_action()), tools)

    assert len(tools.calls) == 1 and formats(llm) == [SELECTOR, WRITER]
    assert "error (not_found): no such customer" in writer_input(llm)


def test_a_port_that_cannot_call_a_tool_says_so(agent):
    class CannotCall(McpToolsPort):
        def list_tools(self, server_name):
            return Tools().list_tools(server_name)

    _, llm, _ = run(agent, selects(tool_action()), CannotCall())

    assert "No tool can be called here" in writer_input(llm)


# ---------------------------------------------------------------- a missing value

def test_a_missing_value_pauses_before_any_tool_call_and_the_answer_resumes_it(agent):
    asking = tool_action(required_inputs=["the customer code"])
    tools = Tools()

    paused, llm, runner = run(agent, selects(asking, next_step=ASKING), tools)

    assert paused.paused is not None and paused.flow == "fast" and tools.calls == []
    assert formats(llm)[0] == SELECTOR and WRITER not in formats(llm)          # no writer yet: the user is asked first (the question is one more call)

    again = ProfileRunner(ScriptedLLM(overrides={CHECK: Script(_verdict("answered", "C-1")), SELECTOR: selects(tool_action()), WRITER: writes()}),
                          MCP_LIST, SessionMetrics(), tools, agent)
    resumed = again.run("dynamics_fast", "C-1", paused=paused.paused)

    assert resumed.paused is None and resumed.reply == "the reply" and tools.calls == [("read_orders", {"customer_no": "C-1"})]


# ---------------------------------------------------------------- the metrics

def test_the_message_records_two_model_calls_the_tool_call_and_the_flow_name(agent):
    tools = Tools()
    _, _, runner = run(agent, selects(tool_action()), tools)

    assert [r.phase_name for r in runner.metrics.request_log] == ["tool_selector", "answer_writer"]
