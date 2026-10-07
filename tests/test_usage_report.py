# pyright: reportOptionalMemberAccess=false, reportArgumentType=false
"""The usage report of every LLM call (Langfuse): what is sent, what it costs, and that it never breaks the agent."""
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.orchestration.support.metrics import SessionMetrics
from application.outbound.ports.usage_ports import CallDetails, UsageReporterPort
from infrastructure.outbound.usage.langfuse import LangfuseUsageReporter
from infrastructure.outbound.usage.prices import billed_output_tokens, cost_usd, load_prices

PRICES = {"gemini-2.5-flash": (0.30, 2.50), "openai/gpt-oss-120b": (0.15, 0.60)}


def reporter():
    return LangfuseUsageReporter("pk", "sk", prices=PRICES, background=False)


class TestTheCost:
    def test_thinking_is_billed_as_output(self):
        # sent 1000, answered 200, total 1700 -> 500 thinking tokens
        assert billed_output_tokens(1000, 200, 1700) == 700
        assert cost_usd(PRICES, "gemini-2.5-flash", 1000, 200, 1700) == pytest.approx((1000 * 0.30 + 700 * 2.50) / 1e6)

    def test_when_the_total_has_no_extra_the_answer_is_the_output(self):
        assert billed_output_tokens(1000, 200, 1200) == 200

    def test_an_unknown_model_has_no_cost(self):
        assert cost_usd(PRICES, "mystery", 10, 10, 20) is None

    def test_the_real_price_files_load(self):
        prices = load_prices()
        assert prices["gemini-2.5-flash"] == (0.30, 2.50) and "openai/gpt-oss-120b" in prices


def spans(payload):
    return payload["resourceSpans"][0]["scopeSpans"][0]["spans"]


def attributes(span):
    return {a["key"]: a["value"]["stringValue"] for a in span["attributes"]}


class TestTheEvents:
    def test_first_call_of_a_message_creates_the_root_span_then_one_generation_per_call(self):
        metrics, r = SessionMetrics(), reporter()
        metrics.begin_message("req-1", "session-1")
        metrics.record(4, "gemini-2.5-flash", 1000, 200, 1700, action_id="a1")
        record = metrics.request_log[0]

        first = spans(r.payload(record, "req-1", "session-1"))
        second = spans(r.payload(record, "req-1", "session-1"))

        assert [attributes(s)["langfuse.observation.type"] for s in first] == ["span", "generation"]
        assert attributes(first[0])["langfuse.session.id"] == "session-1"
        assert first[1]["parentSpanId"] == first[0]["spanId"] and first[1]["traceId"] == first[0]["traceId"]
        assert [attributes(s)["langfuse.observation.type"] for s in second] == ["generation"]
        assert second[0]["parentSpanId"] == first[0]["spanId"]

    def test_ids_are_hex_of_the_size_opentelemetry_needs(self):
        metrics, r = SessionMetrics(), reporter()
        metrics.begin_message("not hex at all", "s")
        metrics.record(1, "gemini-2.5-flash", 10, 5, 15)
        for s in spans(r.payload(metrics.request_log[0], "not hex at all", "s")):
            assert len(s["traceId"]) == 32 and set(s["traceId"]) <= set("0123456789abcdef")
            assert len(s["spanId"]) == 16 and set(s["spanId"]) <= set("0123456789abcdef")

    def test_generation_carries_model_tokens_thinking_and_cost(self):
        metrics, r = SessionMetrics(), reporter()
        metrics.record(4, "gemini-2.5-flash", 1000, 200, 1700, action_id="a1")
        span = spans(r.payload(metrics.request_log[0], "t", "s"))[-1]
        attrs = attributes(span)

        assert span["name"] == "cognitive_worker (a1)" and attrs["gen_ai.request.model"] == "gemini-2.5-flash"
        assert json.loads(attrs["langfuse.observation.usage_details"]) == {"input": 1000, "output": 700, "total": 1700}
        assert attrs["langfuse.observation.metadata.thinking_tokens"] == "500"
        assert json.loads(attrs["langfuse.observation.cost_details"])["total"] == pytest.approx((1000 * 0.30 + 700 * 2.50) / 1e6)

    def test_the_trace_is_named_after_what_the_user_asked_and_the_steps_after_the_phase(self):
        metrics, r = SessionMetrics(), reporter()
        metrics.record(2, "gemini-2.5-flash", 10, 5, 15)
        sent = spans(r.payload(metrics.request_log[0], "t", "s", CallDetails("Plan a  party\nfor 10 people")))
        assert sent[0]["name"] == "Plan a party for 10 people"
        assert attributes(sent[0])["langfuse.trace.name"] == "Plan a party for 10 people"
        assert attributes(sent[0])["langfuse.trace.input"] == "Plan a  party\nfor 10 people"
        assert sent[1]["name"] == "project_manager"

    def test_a_long_question_gives_a_short_name(self):
        metrics, r = SessionMetrics(), reporter()
        metrics.record(1, "gemini-2.5-flash", 10, 5, 15)
        name = spans(r.payload(metrics.request_log[0], "t", "s", CallDetails("word " * 100)))[0]["name"]
        assert len(name) <= 120 and name.endswith("…")

    def test_the_generation_carries_what_was_sent_and_what_came_back(self):
        metrics, r = SessionMetrics(), reporter()
        metrics.record(1, "gemini-2.5-flash", 10, 5, 15)
        generation = spans(r.payload(metrics.request_log[0], "t", "s", CallDetails("hi", "IN", "OUT")))[-1]
        assert attributes(generation)["langfuse.observation.input"] == "IN"
        assert attributes(generation)["langfuse.observation.output"] == "OUT"

    def test_without_details_no_input_or_output_is_sent(self):
        metrics, r = SessionMetrics(), reporter()
        metrics.record(1, "gemini-2.5-flash", 10, 5, 15)
        keys = {k for s in spans(r.payload(metrics.request_log[0], "t", "s")) for k in attributes(s)}
        assert not {k for k in keys if k.endswith((".input", ".output"))}

    def test_an_unpriced_model_is_sent_without_cost(self):
        metrics, r = SessionMetrics(), reporter()
        metrics.record(1, "mystery", 10, 5, 15)
        assert "langfuse.observation.cost_details" not in attributes(spans(r.payload(metrics.request_log[0], "t", "s"))[-1])

    def test_it_goes_to_the_otel_endpoint_with_the_realtime_header(self):
        r = reporter()
        assert r.url.endswith("/api/public/otel/v1/traces")
        assert r.headers["x-langfuse-ingestion-version"] == "4"


class TestTheWiring:
    def test_every_recorded_call_reaches_the_reporter_with_its_message(self):
        class Spy(UsageReporterPort):
            def __init__(self):
                self.seen = []

            def report(self, record, trace_id, session_id, details=None):
                self.seen.append((record.phase_name, trace_id, session_id))

        spy = Spy()
        metrics = SessionMetrics(spy)
        metrics.begin_message("req-9", "s-9")
        metrics.record(1, "m", 1, 1, 2)
        metrics.record(2, "m", 1, 1, 2)
        assert spy.seen == [("triage_specialist", "req-9", "s-9"), ("project_manager", "req-9", "s-9")]

    def test_the_reporter_gets_the_user_message_and_the_payload_and_answer_of_the_call(self):
        seen = []

        class Spy(UsageReporterPort):
            def report(self, record, trace_id, session_id, details=None):
                seen.append(details)

        metrics = SessionMetrics(Spy())
        metrics.begin_message("t", "s", "what the user asked")
        metrics.record(1, "m", 1, 1, 2, input_text="in", output_text="out")
        assert seen == [CallDetails("what the user asked", "in", "out")]

    def test_a_failing_reporter_never_breaks_the_call(self):
        class Broken(UsageReporterPort):
            def report(self, record, trace_id, session_id, details=None):
                raise RuntimeError("down")

        metrics = SessionMetrics(Broken())
        metrics.record(1, "m", 1, 1, 2)
        assert metrics.totals.requests == 1

    def test_without_langfuse_keys_there_is_no_reporter(self, monkeypatch):
        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
        assert LangfuseUsageReporter.from_env() is None

    def test_with_keys_the_host_defaults_to_the_eu_cloud(self, monkeypatch):
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
        monkeypatch.delenv("LANGFUSE_HOST", raising=False)
        r = LangfuseUsageReporter.from_env()
        assert r.url == "https://cloud.langfuse.com/api/public/otel/v1/traces"
        assert r.headers["Authorization"].startswith("Basic ")

    def test_a_uuid_request_id_becomes_a_json_safe_trace_id(self):
        import json
        import uuid
        metrics, r = SessionMetrics(), reporter()
        metrics.begin_message(uuid.uuid4(), "s")
        metrics.record(1, "gemini-2.5-flash", 10, 5, 15)
        json.dumps(r.payload(metrics.request_log[0], metrics.trace_id, "s"))


class TestTheChatName:
    """The name given when the session starts is the group of all its messages in Langfuse."""

    class Recorder(UsageReporterPort):
        def __init__(self):
            self.seen = []

        def report(self, record, trace_id, session_id, details=None):
            self.seen.append((session_id, details.message if details else None))

    def service(self, recorder):
        from application.service.session_service import SessionService
        from test_flow_golden import ScriptedLLM
        return SessionService(outbound_port=ScriptedLLM(), usage_reporter=recorder)

    def talk(self, service, name):
        from application.inbound.dto.session import MessageReceivedRequestDTO, StartSessionRequestDTO
        session = service.start_session(StartSessionRequestDTO(user_id="tester", username="tester", session_name=name)).session_id
        for text in ("first question", "second question"):
            assert service.message_received(MessageReceivedRequestDTO(user_id="tester", session_id=session, message=text)).success
        return session

    def test_every_message_of_the_chat_goes_under_its_name(self):
        recorder = self.Recorder()
        self.talk(self.service(recorder), "Weather chat")
        assert {s for s, _ in recorder.seen} == {"Weather chat"}
        assert {m for _, m in recorder.seen} == {"first question", "second question"}

    def test_without_a_name_the_group_is_the_session_id(self):
        recorder = self.Recorder()
        session = self.talk(self.service(recorder), None)
        assert {s for s, _ in recorder.seen} == {session}

    def test_a_blank_name_counts_as_no_name(self):
        recorder = self.Recorder()
        session = self.talk(self.service(recorder), "   ")
        assert {s for s, _ in recorder.seen} == {session}
