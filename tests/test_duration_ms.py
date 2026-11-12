# T-08.2: every LLM call has its duration in the record and in the log line, so a change that wants to be faster is judged in
# seconds and not by an estimate. No real call, no real wait: the runner takes its clock from an attribute.
import importlib.util
import os
import sys

import pytest

from application.runtime.state.flow_state import FlowState
from application.runtime.step.runner import PhaseRunner
from application.runtime.step.model_selection import ModelResolver
from application.runtime.step.metrics import SessionMetrics
from domain.entities.llm_response.response import Response
from domain.entities.llm_response.tokens_usage import TokensUsage
from step_specs import TRIAGE
from test_fallback import PRIMARY, FALLBACKS, Ask, HttpError, a_response

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Recorder:
    def __init__(self):
        self.records = []

    def info(self, message, **fields):
        self.records.append((message, fields))

    warning = info


class Clock:
    """Each look at the clock is `step` seconds after the one before, so a call that looks at it twice took exactly `step`."""

    def __init__(self, step):
        self.now, self.step = 0.0, step

    def __call__(self):
        value, self.now = self.now, self.now + self.step
        return value


def runner_with(port, step=0.25, models=None):
    metrics = SessionMetrics()
    runner = PhaseRunner(port, metrics, models=ModelResolver({"models": models or [PRIMARY, *FALLBACKS]}), flow_name="identification")
    runner._clock = Clock(step)
    return runner, metrics


def test_a_call_has_its_duration_in_the_record_and_in_the_log_line(monkeypatch):
    log = Recorder()
    monkeypatch.setattr("application.runtime.step.metrics.logger", log)
    runner, metrics = runner_with(Ask({}, default=a_response()))

    runner.run_phase(TRIAGE, FlowState(message="hi"))

    [record] = metrics.request_log
    assert record.duration_ms == 250 and "duration_ms" not in record.to_dict()      # the summary is in the golden file: no time there
    [(message, fields)] = [(m, f) for m, f in log.records if m == "LLM call"]
    assert fields["duration_ms"] == 250
    assert set(fields) == {"profile", "flow", "step", "phase_id", "model", "client", "profile_hash", "prompt_tokens",
                           "completion_tokens", "total_tokens", "cost_usd", "duration_ms"}       # a number, never a text


def test_the_time_of_a_call_that_needed_its_fallback_model_counts_from_the_first_try():
    runner, metrics = runner_with(Ask({PRIMARY: HttpError(503)}, default=a_response()), step=1.0)

    runner.run_phase(TRIAGE, FlowState(message="hi"))

    [record] = metrics.request_log
    assert record.model == FALLBACKS[0] and record.duration_ms == 1000       # one measure for the whole step, not one per try


def test_a_step_that_fails_has_its_time_in_the_log_and_no_text(monkeypatch):
    log = Recorder()
    monkeypatch.setattr("application.runtime.step.runner.logger", log)
    runner, metrics = runner_with(Ask({PRIMARY: HttpError(400, "SECRET-VALUE-IN-AN-ERROR")}), step=0.5)

    with pytest.raises(Exception):
        runner.run_phase(TRIAGE, FlowState(message="hi"))

    [fields] = [f for m, f in log.records if m == "LLM step failed"]
    assert fields["duration_ms"] == 500 and set(fields) == {"phase_id", "model", "error_type", "duration_ms"}
    assert "SECRET-VALUE-IN-AN-ERROR" not in repr(log.records) and metrics.request_log == []


def test_a_record_nobody_timed_has_no_duration_and_adds_nothing():
    metrics = SessionMetrics()
    metrics.record(1, "m", 1, 1, 2)
    metrics.record(1, "m", 1, 1, 2, duration_ms=1500)
    metrics.record(2, "m", 1, 1, 2, duration_ms=500)

    assert [r.duration_ms for r in metrics.request_log] == [None, 1500, 500]
    steps = metrics.duration_by("step")
    assert sum(steps.values()) == 2000 and len(steps) == 2


def test_the_duration_can_be_totalled_by_any_key_a_record_has():
    metrics = SessionMetrics()
    metrics.begin_message("t", "s", "hello", profile="special", flow="special", client="web")
    metrics.record(1, "model-a", 1, 1, 2, duration_ms=300)
    metrics.record(2, "model-b", 1, 1, 2, duration_ms=700)

    assert metrics.duration_by("profile") == {("special",): 1000}
    assert metrics.duration_by("model") == {("model-a",): 300, ("model-b",): 700}
    with pytest.raises(ValueError):
        metrics.duration_by("token")


def test_the_summary_has_no_time_because_it_is_a_deterministic_record_held_by_the_golden_file():
    metrics = SessionMetrics()
    metrics.record(1, "m", 1, 1, 2, duration_ms=42)

    assert "duration_ms" not in metrics.summary()["request_log"][0] and metrics.request_log[0].duration_ms == 42


def script(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(PROJECT_ROOT, "scripts", f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_the_report_of_a_message_lists_its_steps_with_the_seconds_each_took():
    run = script("run_profile")
    metrics = SessionMetrics()
    metrics.record(1, "model-a", 1, 1, 2, duration_ms=3100)
    metrics.record(2, "model-b", 1, 1, 2, duration_ms=6400)

    class Service:
        pass

    service = Service()
    service.metrics = metrics

    steps = run.steps_of([service])

    assert [(s["step"], s["seconds"]) for s in steps] == [("triage_specialist", 3.1), ("project_manager", 6.4)]
