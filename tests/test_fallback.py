# T-04: a model that is out of capacity (429, 5xx, timeout, no connection) is waited for a little and then replaced by the
# fallback models of the active profile; a daily quota that is gone goes to the next model at once. No real call, no real wait.
import json
import os

import pytest

from application.orchestration.engine.phase_runner import PhaseRunner
from application.orchestration.phases.catalog import PHASES
from application.orchestration.phases.identification.triage import TRIAGE
from application.orchestration.state.flow_state import FlowState
from application.orchestration.support import failure as failure_module
from application.orchestration.support.failure import (
    AgentFailure, capacity_problem, daily_quota_used_up, retry_wait_seconds, wait_before_retry,
)
from application.orchestration.support.metrics import SessionMetrics
from application.orchestration.support.model_selection import (
    FALLBACK_VARIABLE, MODELS_FILE_VARIABLE, fallback_models, load_config,
)
from application.outbound.ports.llm_ports import LLMOutboundPort
from domain.entities.llm_response.response import Response
from domain.entities.llm_response.tokens_usage import TokensUsage

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "step_models.json")
DAILY = "Quota exceeded for metric: generate_content_free_tier_requests, limit: 20, Generate content requests per day limit exceeded"


class HttpError(Exception):
    def __init__(self, status, text="boom"):
        super().__init__(text)
        self.status_code = status


class Ask(LLMOutboundPort):
    """Answers by model id: an exception instance to raise, or a Response to return. Records the models it was asked."""

    def __init__(self, by_model, default=None):
        self.by_model, self.default, self.asked = by_model, default, []

    def is_available(self):
        return True

    def ask(self, payload):
        self.asked.append(payload.model.id)
        result = self.by_model.get(payload.model.id, self.default)
        if isinstance(result, BaseException):
            raise result
        return result


def a_response():
    return Response(None, None, None, None, None, tokens_usage=TokensUsage(10, 5, 15))


def send(port, phase_id=1):
    """One call of the triage step through the real PhaseRunner (the model comes from the usual rules)."""
    runner = PhaseRunner(port, SessionMetrics())
    return runner.run_phase(TRIAGE, FlowState(message="hi")), runner


@pytest.fixture
def chosen(monkeypatch):
    """The model of phase 1 (the code default) and two fallbacks."""
    from application.orchestration.support.model_selection import model_for_phase
    primary = model_for_phase(1, PHASES[1].default_model).id
    monkeypatch.setenv(FALLBACK_VARIABLE, "gemini-3.5-flash-lite,gemini-3-flash-preview")
    return primary


# ---------------------------------------------------------------- what counts as a lack of capacity

@pytest.mark.parametrize("error, expected", [
    (HttpError(429), True), (HttpError(500), True), (HttpError(503), True), (TimeoutError(), True),
    (ConnectionError(), True), (HttpError(400), False), (HttpError(401), False), (HttpError(404), False),
    (ValueError("bad json"), False), (RuntimeError("?"), False),
])
def test_capacity_problem(error, expected):
    assert capacity_problem(error) is expected


def test_only_a_429_that_says_per_day_is_a_used_up_quota():
    assert daily_quota_used_up(HttpError(429, DAILY)) is True
    assert daily_quota_used_up(HttpError(429, "too many requests per minute")) is False
    assert daily_quota_used_up(HttpError(503, "per day")) is False


# ---------------------------------------------------------------- the wait

def test_the_wait_doubles_is_capped_and_only_follows_a_lack_of_capacity(monkeypatch):
    slept = []
    monkeypatch.setattr(failure_module.time, "sleep", slept.append)
    monkeypatch.setenv("AI_AGENT_RETRY_WAIT_SECONDS", "2")
    for attempt in (1, 2, 3, 4, 5):
        wait_before_retry(attempt, HttpError(503))
    wait_before_retry(1, ValueError("bad answer"))
    wait_before_retry(1, HttpError(400))
    assert slept == [2, 4, 8, 16, 16]


@pytest.mark.parametrize("value, seconds", [("0", 0.0), ("0.5", 0.5), ("-3", 0.0), ("soon", 1.0)])
def test_the_wait_setting(monkeypatch, value, seconds):
    monkeypatch.setenv("AI_AGENT_RETRY_WAIT_SECONDS", value)
    assert retry_wait_seconds() == seconds


# ---------------------------------------------------------------- the fallback

def test_a_model_out_of_capacity_is_replaced_by_the_first_fallback_that_answers(chosen):
    port = Ask({chosen: HttpError(503), "gemini-3.5-flash-lite": HttpError(503)}, default=a_response())
    answer, runner = send(port)
    assert isinstance(answer, Response)
    assert port.asked == [chosen] * 3 + ["gemini-3.5-flash-lite", "gemini-3-flash-preview"]


def test_the_metrics_name_the_model_that_answered(chosen):
    port = Ask({chosen: HttpError(503)}, default=a_response())
    _, runner = send(port)
    models = {m for per_phase in runner.metrics.by_phase.values() for m in per_phase}
    assert models == {"gemini-3.5-flash-lite"}


def test_a_used_up_daily_quota_goes_to_the_fallback_without_more_tries(chosen):
    port = Ask({chosen: HttpError(429, DAILY)}, default=a_response())
    send(port)
    assert port.asked == [chosen, "gemini-3.5-flash-lite"]


def test_an_error_that_is_not_a_lack_of_capacity_never_falls_back(chosen):
    for error in (HttpError(401), HttpError(400), HttpError(404)):
        port = Ask({chosen: error}, default=a_response())
        with pytest.raises(AgentFailure):
            send(port)
        assert "gemini-3.5-flash-lite" not in port.asked


def test_when_every_model_fails_the_failure_is_the_chosen_models(chosen):
    port = Ask({}, default=HttpError(503))
    with pytest.raises(AgentFailure) as raised:
        send(port)
    assert raised.value.category == "unknown" and isinstance(raised.value.cause, HttpError)
    assert port.asked == [chosen] * 3 + ["gemini-3.5-flash-lite", "gemini-3-flash-preview"]


def test_a_rate_limit_that_nothing_answers_is_reported_as_a_rate_limit(chosen):
    port = Ask({}, default=HttpError(429, "slow down"))
    with pytest.raises(AgentFailure) as raised:
        send(port)
    assert raised.value.category == "rate_limit"


def test_the_chosen_model_in_the_list_is_not_asked_again(monkeypatch):
    from application.orchestration.support.model_selection import model_for_phase
    primary = model_for_phase(1, PHASES[1].default_model).id
    monkeypatch.setenv(FALLBACK_VARIABLE, f"{primary},gemini-3-flash-preview")
    port = Ask({primary: HttpError(503)}, default=a_response())
    send(port)
    assert port.asked == [primary] * 3 + ["gemini-3-flash-preview"]


def test_no_fallback_models_means_the_old_behaviour(monkeypatch):
    monkeypatch.setenv(FALLBACK_VARIABLE, "")
    from application.orchestration.support.model_selection import model_for_phase
    primary = model_for_phase(1, PHASES[1].default_model).id
    port = Ask({primary: HttpError(503)}, default=a_response())
    with pytest.raises(AgentFailure):
        send(port)
    assert port.asked == [primary] * 3


def test_a_success_never_looks_at_the_fallbacks(chosen):
    port = Ask({}, default=a_response())
    send(port)
    assert port.asked == [chosen]


# ---------------------------------------------------------------- which models are the fallbacks

def test_the_variable_wins_and_skips_ids_that_are_not_in_the_catalog(monkeypatch):
    monkeypatch.setenv(FALLBACK_VARIABLE, " gemini-3-flash-preview , not-a-model ,")
    assert [m.id for m in fallback_models()] == ["gemini-3-flash-preview"]


def test_without_a_variable_or_a_config_there_are_none():
    assert fallback_models() == []


def test_the_shipped_google_profiles_name_free_tier_fallbacks(monkeypatch):
    monkeypatch.setenv(MODELS_FILE_VARIABLE, CONFIG_PATH)
    config = load_config()
    free = {m["id"] for m in json.load(open(os.path.join(os.path.dirname(CONFIG_PATH), "gemini_models.json"), encoding="utf-8"))["models"] if m["free_tier"]}
    for name in ("proven", "google_free"):
        ids = config["profiles"][name]["fallback_models"]
        assert ids and set(ids) <= free, name
    assert [m.id for m in fallback_models()] == config["profiles"]["proven"]["fallback_models"]


def test_the_claude_profiles_never_fall_back_to_another_provider(monkeypatch):
    # customer data must not move to the Google free tier (it trains Google's products) because Claude had a bad minute
    monkeypatch.setenv(MODELS_FILE_VARIABLE, CONFIG_PATH)
    for name in ("claude_haiku", "claude_mixed", "claude_sonnet"):
        assert "fallback_models" not in load_config()["profiles"][name]


def test_a_config_with_a_bad_fallback_fails_loudly(tmp_path, monkeypatch):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"profile": "p", "profiles": {"p": {"default": "gemini-3.1-flash-lite", "fallback_models": ["nope"]}}}), encoding="utf-8")
    monkeypatch.setenv(MODELS_FILE_VARIABLE, str(path))
    with pytest.raises(ValueError, match="fallback_models"):
        load_config()
    path.write_text(json.dumps({"profile": "p", "profiles": {"p": {"fallback_models": "gemini-3.1-flash-lite"}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="list of model ids"):
        load_config()
