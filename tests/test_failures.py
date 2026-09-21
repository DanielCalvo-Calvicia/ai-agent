"""Failures: retries, the setting that controls them, and the apology that tells the user what happened."""
import json
import os
import sys
from typing import List

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.orchestration.failure import (
    AgentFailure,
    apology,
    apology_for_unexpected,
    classify,
    max_attempts,
    worth_retrying,
)
from application.orchestration.metrics import SessionMetrics
from application.orchestration.phase_runner import PhaseRunner
from application.service.session_service import SessionService
from domain.entities.payload import Payload
from infrastructure.outbound.llm.response_mapper import build_response

from test_flow_golden import (
    GATE, PM, SCENARIOS, ScriptedLLM, _action, _plan, _run,
)

USAGE = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}


@pytest.fixture(autouse=True)
def _project_cwd(monkeypatch):
    monkeypatch.chdir(PROJECT_ROOT)
    monkeypatch.delenv("AI_AGENT_MAX_ATTEMPTS", raising=False)


class HttpError(Exception):
    def __init__(self, status_code):
        super().__init__(f"http {status_code} with secret-looking body sk-123")
        self.status_code = status_code


class APIConnectionError(Exception):
    pass


class ReadTimeout(Exception):
    pass


# ===============================================
#  SETTING AND CLASSIFICATION
# ===============================================

class TestSetting:
    def test_default_is_three(self):
        assert max_attempts() == 3

    def test_the_variable_changes_it(self, monkeypatch):
        monkeypatch.setenv("AI_AGENT_MAX_ATTEMPTS", "5")
        assert max_attempts() == 5

    @pytest.mark.parametrize("value,expected", [("0", 1), ("-2", 1), ("abc", 3), ("", 3)])
    def test_bad_values_are_handled(self, monkeypatch, value, expected):
        monkeypatch.setenv("AI_AGENT_MAX_ATTEMPTS", value)
        assert max_attempts() == expected


class TestClassify:
    @pytest.mark.parametrize("error,category", [
        (HttpError(429), "rate_limit"),
        (HttpError(401), "auth"),
        (HttpError(403), "auth"),
        (HttpError(404), "not_found"),
        (HttpError(400), "bad_request"),
        (APIConnectionError("x"), "connection"),
        (ConnectionError("x"), "connection"),
        (ReadTimeout("x"), "timeout"),
        (json.JSONDecodeError("bad", "doc", 0), "bad_answer"),
        (ValueError("domain must be one of"), "bad_answer"),
        (KeyError("prompt_tokens"), "bad_answer"),
        (RuntimeError("?"), "unknown"),
        (HttpError(500), "unknown"),
    ])
    def test_category(self, error, category):
        assert classify(error) == category

    @pytest.mark.parametrize("status,retry", [(400, False), (401, False), (403, False), (404, False),
                                              (429, True), (500, True), (None, True)])
    def test_only_errors_that_can_get_better_are_retried(self, status, retry):
        error = HttpError(status) if status else RuntimeError("x")
        assert worth_retrying(error) is retry


class TestApology:
    def test_it_says_what_happened_why_and_when(self):
        text = apology("connection", 2)
        assert text.startswith("Sorry")
        assert "What happened: I could not reach the language model service while planning the steps." in text
        assert "Why: the network or the service is down." in text

    def test_every_category_has_an_explanation(self):
        for category in ("connection", "timeout", "rate_limit", "auth", "not_found", "bad_request",
                         "bad_answer", "reported_error", "unknown"):
            assert "What happened:" in apology(category) and "Why:" in apology(category)

    def test_an_unknown_category_falls_back_to_the_general_apology(self):
        assert AgentFailure("nonsense").category == "unknown"

    def test_raw_error_text_is_never_included(self):
        failure = AgentFailure("auth", 1, HttpError(401))
        assert "sk-123" not in failure.apology() and "sk-123" not in failure.explanation()

    def test_an_unexpected_error_gets_the_general_apology(self):
        assert "something unexpected" in apology_for_unexpected(RuntimeError("boom"))

    def test_an_agent_failure_gets_its_own_apology(self):
        assert "took too long" in apology_for_unexpected(AgentFailure("timeout", 4))


# ===============================================
#  RETRIES OF A CALL
# ===============================================

class FlakyLLM(ScriptedLLM):
    """Fails `failures` times with `error`, then answers."""

    def __init__(self, failures, error):
        super().__init__()
        self.failures, self.error, self.tries = failures, error, 0

    def ask(self, Payload: Payload):
        self.tries += 1
        if self.tries <= self.failures:
            raise self.error
        return super().ask(Payload)


def _send(llm):
    from application.orchestration.phases.triage import TRIAGE
    from application.orchestration.flow_state import FlowState
    runner = PhaseRunner(llm, SessionMetrics())
    return runner.run_phase(TRIAGE, FlowState(message="hi"))


class TestCallRetries:
    def test_a_call_that_works_the_second_time_succeeds(self):
        llm = FlakyLLM(1, APIConnectionError("x"))
        assert _send(llm).user_goal is not None
        assert llm.tries == 2

    def test_a_call_is_tried_as_many_times_as_the_setting(self, monkeypatch):
        monkeypatch.setenv("AI_AGENT_MAX_ATTEMPTS", "4")
        llm = FlakyLLM(99, APIConnectionError("x"))
        with pytest.raises(AgentFailure) as failure:
            _send(llm)
        assert llm.tries == 4
        assert failure.value.category == "connection" and failure.value.phase_id == 1

    def test_a_bad_request_is_not_retried(self):
        llm = FlakyLLM(99, HttpError(400))
        with pytest.raises(AgentFailure) as failure:
            _send(llm)
        assert llm.tries == 1 and failure.value.category == "bad_request"

    def test_an_answer_that_is_not_json_is_retried_and_reported(self):
        llm = FlakyLLM(99, json.JSONDecodeError("bad", "doc", 0))
        with pytest.raises(AgentFailure) as failure:
            _send(llm)
        assert llm.tries == 3 and failure.value.category == "bad_answer"

    def test_only_successful_calls_are_counted_in_the_metrics(self):
        llm = FlakyLLM(2, APIConnectionError("x"))
        runner = PhaseRunner(llm, SessionMetrics())
        from application.orchestration.phases.triage import TRIAGE
        from application.orchestration.flow_state import FlowState
        runner.run_phase(TRIAGE, FlowState(message="hi"))
        assert runner.metrics.totals.requests == 1


# ===============================================
#  WHAT THE FLOW DOES WITH A FAILURE
# ===============================================

class FailOnPhase(ScriptedLLM):
    def __init__(self, format_prefix, error, **kwargs):
        super().__init__(**kwargs)
        self.format_prefix, self.error = format_prefix, error

    def ask(self, Payload: Payload):
        if Payload.response_format and Payload.response_format.name.startswith(self.format_prefix):
            self.calls.append({"format": Payload.response_format.name})
            raise self.error
        return super().ask(Payload)


def _say(llm, text="hi") -> "object":
    from application.inbound.dto.session import MessageReceivedRequestDTO, StartSessionRequestDTO
    service = SessionService(outbound_port=llm, mcp_list=[])
    session_id = service.start_session(StartSessionRequestDTO(user_id="tester", username="t")).session_id
    return service.message_received(MessageReceivedRequestDTO(user_id="tester", session_id=session_id, message=text))


class TestFlowFailures:
    def test_the_apology_names_the_phase_that_failed(self):
        result = _say(FailOnPhase("project_manager", APIConnectionError("x")))
        assert result.success is False
        assert "while planning the steps" in result.response
        assert "could not reach the language model service" in result.response

    def test_the_failed_phase_was_tried_the_configured_number_of_times(self, monkeypatch):
        monkeypatch.setenv("AI_AGENT_MAX_ATTEMPTS", "2")
        llm = FailOnPhase("project_manager", APIConnectionError("x"))
        _say(llm)
        assert [c["format"] for c in llm.calls].count("project_manager_phase2_response_format") == 2

    def test_a_step_that_cannot_be_done_fails_only_that_step(self):
        llm = FailOnPhase("phase4", APIConnectionError("x"),
                          overrides={PM: _plan(_action("1"), _action("2", dependencies=["1"]))})
        result = _say(llm)
        assert result.success is True                                   # the answer is still written
        draft = next(c for c in llm.calls if c["format"].startswith("draft"))["user_message"]
        assert "could not reach the language model service" in draft
        assert "skipped because a step it needs failed" in draft

    def test_a_failed_message_is_not_remembered(self):
        from application.inbound.dto.session import MessageReceivedRequestDTO, StartSessionRequestDTO
        service = SessionService(outbound_port=FailOnPhase("triage", APIConnectionError("x")), mcp_list=[])
        sid = service.start_session(StartSessionRequestDTO(user_id="tester", username="t")).session_id
        service.message_received(MessageReceivedRequestDTO(user_id="tester", session_id=sid, message="hi"))
        assert service.sessions[sid].history == []


def _retry_step(status):
    return {"ready_to_execute": False, "status": status, "recommended_action": "again",
            "blocking_reason": "", "requested_user_input": []}


class TestStatusRetry:
    def test_a_phase_that_says_retry_is_run_again(self):
        answers = iter([_retry_step("retry"), None])

        def gate(payload):
            step = next(answers)
            return None if step is None else {
                "safety_and_validation": {"sensitive": False, "requires_confirmation": False}, "next_step": step}

        llm = ScriptedLLM(overrides={GATE: gate})
        result = _say(llm)
        assert result.success is True and result.response == "final answer"
        assert [c["format"] for c in llm.calls].count(GATE) == 2

    def test_a_phase_that_keeps_saying_error_ends_with_an_apology(self):
        llm = ScriptedLLM(overrides={GATE: {
            "safety_and_validation": {"sensitive": False, "requires_confirmation": False},
            "next_step": _retry_step("error")}})
        result = _say(llm)
        assert result.success is False
        assert "one of my steps reported an error" in result.response
        assert "while checking that the plan is safe" in result.response
        assert [c["format"] for c in llm.calls].count(GATE) == 3
