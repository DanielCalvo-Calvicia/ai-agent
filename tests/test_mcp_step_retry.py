# pyright: reportOptionalMemberAccess=false, reportIncompatibleMethodOverride=false
"""A step whose tool failed for good is not asked again; a step that simply produced nothing still is (AI_AGENT_MAX_ATTEMPTS)."""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.orchestration.engine.pipeline import Pipeline
from application.orchestration.support.metrics import SessionMetrics
from application.orchestration.flows.action_executor import MAX_TOOL_WAIT_SECONDS
from application.outbound.ports.mcp_ports import remaining_tool_wait, report_final_tool_failure, watch_tool_failures
from flow_trace import FULL_FLOW
from test_flow_golden import PM, ScriptedLLM, _action, _no_result, _plan

PHASE5 = "phase5_single_action_response_format"


def run(monkeypatch, tool_failure):
    """One tool action whose step never produces an output; `tool_failure` says whether its tool failed for good."""
    monkeypatch.setenv("AI_AGENT_MAX_ATTEMPTS", "3")

    def answer(payload):
        if tool_failure:
            report_final_tool_failure()
        return _no_result(payload)

    llm = ScriptedLLM(overrides={PM: _plan(_action("1", "mcp_tool_call")), PHASE5: answer})
    mcp_list = [{"name": "aws_microservice", "type": "sse", "config": {"type": "sse", "url": "http://x"}}]
    Pipeline(llm, mcp_list, SessionMetrics(), flow=FULL_FLOW).run("do it")
    return sum(1 for call in llm.calls if call["format"] == PHASE5)


def test_a_step_with_no_result_is_asked_again_up_to_the_attempts(monkeypatch):
    assert run(monkeypatch, tool_failure=False) == 3


def test_a_step_whose_tool_failed_for_good_is_asked_once(monkeypatch):
    assert run(monkeypatch, tool_failure=True) == 1


def test_reporting_outside_a_watched_step_does_nothing():
    report_final_tool_failure()


def test_each_attempt_is_watched_on_its_own():
    with watch_tool_failures() as first:
        report_final_tool_failure()
    with watch_tool_failures() as second:
        pass
    assert first.final is True and second.final is False


def test_the_run_of_a_message_gives_its_tools_60_seconds_in_total():
    seen = []

    def answer(payload):
        seen.append(remaining_tool_wait())
        return {"actions": [{**_action("1", "mcp_tool_call"), "output": "done"}]}

    llm = ScriptedLLM(overrides={PM: _plan(_action("1", "mcp_tool_call")), PHASE5: answer})
    mcp_list = [{"name": "aws_microservice", "type": "sse", "config": {"type": "sse", "url": "http://x"}}]
    Pipeline(llm, mcp_list, SessionMetrics(), flow=FULL_FLOW).run("do it")

    assert len(seen) == 1 and 59 < seen[0] <= MAX_TOOL_WAIT_SECONDS == 60
    assert remaining_tool_wait() is None                      # and it does not outlive the run
