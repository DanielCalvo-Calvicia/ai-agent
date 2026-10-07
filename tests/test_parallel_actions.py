# pyright: reportOptionalMemberAccess=false, reportIncompatibleMethodOverride=false
"""Independent actions can run at the same time (AI_AGENT_PARALLEL_ACTIONS) without changing what the plan produces."""
import os
import sys
import threading
import time

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.orchestration.support.metrics import SessionMetrics
from application.orchestration.engine.pipeline import Pipeline
from application.outbound.ports.usage_ports import UsageReporterPort
from flow_trace import FULL_FLOW
from test_flow_golden import ScriptedLLM, _ACTION_ID, _action, _plan

DELAY = 0.15


def plan():
    """1, 2, 3 need nothing; 4 needs 1 and 2; 5 has subactions 5.1 and 5.2 and needs 3; 6 is a tool call."""
    return _plan(
        _action("1"), _action("2"), _action("3"),
        _action("4", dependencies=["1", "2"]),
        _action("5", dependencies=["3"], subactions=[_action("5.1"), _action("5.2")]),
        _action("6", "mcp_tool_call"),
    )


class Slow(ScriptedLLM):
    """Every worker and tool call takes DELAY seconds; it notes how many calls overlap and the order they finished in."""

    def __init__(self):
        super().__init__(overrides={"project_manager_phase2_response_format": plan()})
        self.lock = threading.Lock()
        self.running = 0
        self.max_running = 0
        self.finished = []
        self.tool_overlap = False

    def ask(self, payload):
        name = payload.response_format.name if payload.response_format else ""
        if not name.startswith(("phase4", "phase5")):
            return super().ask(payload)
        found = _ACTION_ID.search(payload.message.content).group(1)
        with self.lock:
            self.running += 1
            self.max_running = max(self.max_running, self.running)
            if name.startswith("phase5") and self.running > 1:
                self.tool_overlap = True
        time.sleep(DELAY)
        try:
            return super().ask(payload)
        finally:
            with self.lock:
                self.running -= 1
                self.finished.append(found)


def run(monkeypatch, parallel, reporter=None):
    if parallel is not None:
        monkeypatch.setenv("AI_AGENT_PARALLEL_ACTIONS", str(parallel))
    llm, metrics = Slow(), SessionMetrics(reporter)
    started = time.time()
    result = Pipeline(llm, [{"name": "aws_microservice", "type": "sse", "config": {"type": "sse", "url": "http://x"}}],
                      metrics, flow=FULL_FLOW).run("do it")
    return llm, metrics, result, time.time() - started


def workers(metrics):
    return [r.action_id for r in metrics.request_log if r.phase_name in ("cognitive_worker", "mcp_operator", "data_engineer")]


class TestParallel:
    def test_by_default_actions_run_one_after_another(self, monkeypatch):
        llm, _, _, _ = run(monkeypatch, None)
        assert llm.max_running == 1

    def test_independent_actions_overlap_and_the_run_is_faster(self, monkeypatch):
        _, _, _, serial = run(monkeypatch, 1)
        llm, _, _, parallel = run(monkeypatch, 4)
        assert llm.max_running >= 3
        assert parallel < serial * 0.75

    def test_the_limit_is_respected(self, monkeypatch):
        llm, _, _, _ = run(monkeypatch, 2)
        assert llm.max_running == 2

    def test_the_result_is_the_same_as_one_after_another(self, monkeypatch):
        _, m1, r1, _ = run(monkeypatch, 1)
        _, m4, r4, _ = run(monkeypatch, 4)
        assert r1.reply == r4.reply
        assert sorted(x for x in workers(m1) if x) == sorted(x for x in workers(m4) if x)
        assert (m1.totals.requests, m1.totals.total) == (m4.totals.requests, m4.totals.total)

    def test_nothing_runs_before_what_it_needs(self, monkeypatch):
        llm, _, _, _ = run(monkeypatch, 6)
        done = llm.finished
        assert done.index("4") > max(done.index("1"), done.index("2"))
        assert done.index("5") > max(done.index("5.1"), done.index("5.2"), done.index("3"))

    def test_tool_calls_never_overlap_with_anything(self, monkeypatch):
        llm, _, _, _ = run(monkeypatch, 6)
        assert llm.tool_overlap is False

    def test_a_bad_value_means_one_at_a_time(self, monkeypatch):
        llm, _, _, _ = run(monkeypatch, "many")
        assert llm.max_running == 1


class TestTiming:
    def test_every_call_reports_when_it_started_and_ended(self, monkeypatch):
        seen = []

        class Spy(UsageReporterPort):
            def report(self, record, trace_id, session_id, details=None):
                seen.append(details)

        run(monkeypatch, 1, Spy())
        assert seen and all(d.started_ns and d.ended_ns and d.ended_ns >= d.started_ns for d in seen)
        assert max((d.ended_ns - d.started_ns) for d in seen) >= DELAY * 1e9 * 0.9      # the slow worker calls

    def test_langfuse_gets_the_real_start_and_end(self):
        from application.orchestration.support.metrics import SessionMetrics as M
        from application.outbound.ports.usage_ports import CallDetails
        from infrastructure.outbound.usage.langfuse import LangfuseUsageReporter
        r = LangfuseUsageReporter("pk", "sk", prices={}, background=False)
        m = M()
        m.record(1, "x", 1, 1, 2)
        span = r.payload(m.request_log[0], "t", "s", CallDetails("q", None, None, 1_000, 5_000))["resourceSpans"][0]["scopeSpans"][0]["spans"][-1]
        assert (span["startTimeUnixNano"], span["endTimeUnixNano"]) == ("1000", "5000")
