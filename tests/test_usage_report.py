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

PRICES = {"gemini-3.5-flash-lite": (0.30, 2.50), "openai/gpt-oss-120b": (0.15, 0.60)}


def reporter():
    return LangfuseUsageReporter("pk", "sk", prices=PRICES, background=False)


class TestTheCost:
    def test_thinking_is_billed_as_output(self):
        # sent 1000, answered 200, total 1700 -> 500 thinking tokens
        assert billed_output_tokens(1000, 200, 1700) == 700
        assert cost_usd(PRICES, "gemini-3.5-flash-lite", 1000, 200, 1700) == pytest.approx((1000 * 0.30 + 700 * 2.50) / 1e6)

    def test_when_the_total_has_no_extra_the_answer_is_the_output(self):
        assert billed_output_tokens(1000, 200, 1200) == 200

    def test_an_unknown_model_has_no_cost(self):
        assert cost_usd(PRICES, "mystery", 10, 10, 20) is None

    def test_the_real_price_files_load(self):
        prices = load_prices()
        assert prices["gemini-3.5-flash-lite"] == (0.30, 2.50) and "openai/gpt-oss-120b" in prices


def spans(payload):
    return payload["resourceSpans"][0]["scopeSpans"][0]["spans"]


def attributes(span):
    return {a["key"]: a["value"]["stringValue"] for a in span["attributes"]}


class TestTheEvents:
    def test_first_call_of_a_message_creates_the_root_span_then_one_generation_per_call(self):
        metrics, r = SessionMetrics(), reporter()
        metrics.begin_message("req-1", "session-1")
        metrics.record(4, "gemini-3.5-flash-lite", 1000, 200, 1700, action_id="a1")
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
        metrics.record(1, "gemini-3.5-flash-lite", 10, 5, 15)
        for s in spans(r.payload(metrics.request_log[0], "not hex at all", "s")):
            assert len(s["traceId"]) == 32 and set(s["traceId"]) <= set("0123456789abcdef")
            assert len(s["spanId"]) == 16 and set(s["spanId"]) <= set("0123456789abcdef")

    def test_generation_carries_model_tokens_thinking_and_cost(self):
        metrics, r = SessionMetrics(), reporter()
        metrics.record(4, "gemini-3.5-flash-lite", 1000, 200, 1700, action_id="a1")
        span = spans(r.payload(metrics.request_log[0], "t", "s"))[-1]
        attrs = attributes(span)

        assert span["name"] == "cognitive_worker (a1)" and attrs["gen_ai.request.model"] == "gemini-3.5-flash-lite"
        assert json.loads(attrs["langfuse.observation.usage_details"]) == {"input": 1000, "output": 700, "total": 1700}
        assert attrs["langfuse.observation.metadata.thinking_tokens"] == "500"
        assert json.loads(attrs["langfuse.observation.cost_details"])["total"] == pytest.approx((1000 * 0.30 + 700 * 2.50) / 1e6)

    def test_the_trace_is_named_after_what_the_user_asked_and_the_steps_after_the_phase(self):
        metrics, r = SessionMetrics(), reporter()
        metrics.record(2, "gemini-3.5-flash-lite", 10, 5, 15)
        sent = spans(r.payload(metrics.request_log[0], "t", "s", CallDetails("Plan a  party\nfor 10 people")))
        assert sent[0]["name"] == "Plan a party for 10 people"
        assert attributes(sent[0])["langfuse.trace.name"] == "Plan a party for 10 people"
        assert attributes(sent[0])["langfuse.trace.input"] == "Plan a  party\nfor 10 people"
        assert sent[1]["name"] == "project_manager"

    def test_a_long_question_gives_a_short_name(self):
        metrics, r = SessionMetrics(), reporter()
        metrics.record(1, "gemini-3.5-flash-lite", 10, 5, 15)
        name = spans(r.payload(metrics.request_log[0], "t", "s", CallDetails("word " * 100)))[0]["name"]
        assert len(name) <= 120 and name.endswith("…")

    def test_the_generation_carries_what_was_sent_and_what_came_back(self):
        metrics, r = SessionMetrics(), reporter()
        metrics.record(1, "gemini-3.5-flash-lite", 10, 5, 15)
        generation = spans(r.payload(metrics.request_log[0], "t", "s", CallDetails("hi", "IN", "OUT")))[-1]
        assert attributes(generation)["langfuse.observation.input"] == "IN"
        assert attributes(generation)["langfuse.observation.output"] == "OUT"

    def test_without_details_no_input_or_output_is_sent(self):
        metrics, r = SessionMetrics(), reporter()
        metrics.record(1, "gemini-3.5-flash-lite", 10, 5, 15)
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
        metrics.record(1, "gemini-3.5-flash-lite", 10, 5, 15)
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



# ---------------------------------------------------------------- MCP tool calls

from application.orchestration.engine.pipeline import Pipeline
from application.outbound.ports.mcp_ports import ToolCallRecord, report_tool_call
from flow_trace import FULL_FLOW
from test_flow_golden import PM, ScriptedLLM, _action, _plan

SECRET = "CUSTOMER-PLACEHOLDER-123"


def a_call(outcome="ok"):
    return ToolCallRecord("customer_orders", outcome, 1234, 1, 1_000_000_000, 2_234_000_000)


class Collecting(UsageReporterPort):
    def __init__(self):
        self.calls = []

    def report(self, record, trace_id, session_id, details=None):
        pass

    def report_tool_call(self, call, trace_id, session_id, details=None):
        self.calls.append((call, trace_id, session_id))


class TestTheToolCalls:
    def test_the_metrics_keep_the_calls_of_the_message_next_to_the_tokens(self):
        metrics = SessionMetrics()
        metrics.record(1, "gemini-3.5-flash-lite", 10, 5, 15)
        metrics.record_tool_call(a_call())
        metrics.record_tool_call(a_call("timeout"))

        assert [c.outcome for c in metrics.tool_calls] == ["ok", "timeout"]
        assert metrics.summary()["tool_calls"] == [
            {"tool": "customer_orders", "outcome": "ok", "duration_ms": 1234, "attempts": 1},
            {"tool": "customer_orders", "outcome": "timeout", "duration_ms": 1234, "attempts": 1},
        ]
        assert metrics.summary()["total_requests"] == 1          # a tool call is not an LLM request

    def test_the_call_reaches_the_reporter_with_its_message(self):
        reporter_ = Collecting()
        metrics = SessionMetrics(reporter_)
        metrics.begin_message("req-1", "session-1", "what is the state of the order?")
        metrics.record_tool_call(a_call())

        assert reporter_.calls == [(a_call(), "req-1", "session-1")]

    def test_a_reporter_that_fails_does_not_break_the_call(self):
        class Broken(UsageReporterPort):
            def report(self, *args, **kwargs):
                raise RuntimeError("down")

            def report_tool_call(self, *args, **kwargs):
                raise RuntimeError("down")

        metrics = SessionMetrics(Broken())
        metrics.record_tool_call(a_call())
        assert len(metrics.tool_calls) == 1

    def test_a_reporter_that_knows_nothing_of_tool_calls_is_fine(self):
        class OldReporter(UsageReporterPort):
            def report(self, *args, **kwargs):
                pass

        metrics = SessionMetrics(OldReporter())
        metrics.record_tool_call(a_call())
        assert len(metrics.tool_calls) == 1

    def test_langfuse_gets_a_span_named_after_the_tool_with_outcome_and_duration_and_no_input_or_output(self):
        r = reporter()
        payload = r.tool_call_payload(a_call("not_found"), "req-1", "session-1", CallDetails("the question", None, None, 1, 2))
        root, tool = spans(payload)
        attrs = attributes(tool)

        assert tool["name"] == "customer_orders" and tool["parentSpanId"] == root["spanId"]
        assert attrs["langfuse.observation.type"] == "span"
        assert attrs["langfuse.observation.metadata.outcome"] == "not_found"
        assert attrs["langfuse.observation.metadata.duration_ms"] == "1234"
        assert attrs["langfuse.observation.level"] == "ERROR"
        assert not any(k.endswith((".input", ".output")) for k in attrs)
        assert tool["startTimeUnixNano"] == "1000000000" and tool["endTimeUnixNano"] == "2234000000"

    def test_a_successful_call_is_not_marked_as_an_error(self):
        [root, tool] = spans(reporter().tool_call_payload(a_call(), "req-2", "s"))
        assert "langfuse.observation.level" not in attributes(tool)

    def test_the_root_span_is_created_once_whichever_comes_first(self):
        metrics, r = SessionMetrics(), reporter()
        metrics.record(4, "gemini-3.5-flash-lite", 10, 5, 15)

        first = spans(r.tool_call_payload(a_call(), "req-3", "s"))
        then = spans(r.payload(metrics.request_log[0], "req-3", "s"))

        assert [attributes(x)["langfuse.observation.type"] for x in first] == ["span", "span"]
        assert [attributes(x)["langfuse.observation.type"] for x in then] == ["generation"]
        assert then[0]["parentSpanId"] == first[0]["spanId"]

    def test_the_queue_failing_does_not_break_the_call(self):
        r = reporter()
        r.queue = None
        r.report_tool_call(a_call(), "t", "s")                    # raises inside, logs, returns

    def test_a_step_hands_the_calls_made_inside_it_to_the_metrics(self, monkeypatch):
        """The adapter reports each call while the step runs; the action loop moves them into the metrics."""
        monkeypatch.setenv("AI_AGENT_MAX_ATTEMPTS", "1")

        def phase5(payload):
            report_tool_call(a_call())
            return {"actions": [{**_action("1", "mcp_tool_call"), "output": "done"}]}

        llm = ScriptedLLM(overrides={PM: _plan(_action("1", "mcp_tool_call")),
                                     "phase5_single_action_response_format": phase5})
        metrics = SessionMetrics()
        mcp_list = [{"name": "aws_microservice", "type": "sse", "config": {"type": "sse", "url": "http://x"}}]
        Pipeline(llm, mcp_list, metrics, flow=FULL_FLOW).run("do it")

        assert [c.tool for c in metrics.tool_calls] == ["customer_orders"]
        assert SECRET not in repr(metrics.summary())
