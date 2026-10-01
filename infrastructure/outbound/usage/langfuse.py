"""
Sends every LLM call to Langfuse (langfuse.com) to see, per message: model, tokens (thinking included) and cost.
Uses Langfuse's OpenTelemetry endpoint (OTLP over HTTP/JSON) directly, so it needs no package: the older ingestion API
is deprecated and new Langfuse projects do not show its data live. Each user message is a trace (a root span named after
what the user asked) and each LLM call a `generation` named after its step, with the payload sent (input) and the answer
(output). That includes the user's text and the prompts: only use a Langfuse project you trust with them.
A failed send is logged and dropped; it never touches the agent.
"""
import base64
import hashlib
import json
import os
import queue
import threading
import time
import urllib.request
import uuid
from typing import Any, Dict, List, Optional, Tuple

from application.orchestration.support.metrics import RequestRecord
from application.outbound.ports.usage_ports import CallDetails, UsageReporterPort
from infrastructure.outbound.usage.prices import billed_output_tokens, cost_usd, load_prices
from shared_logging import get_logger

logger = get_logger(__name__)

DEFAULT_HOST = "https://cloud.langfuse.com"
SERVICE_NAME = "oblivion-ai-agent"
MAX_NAME_CHARS = 120


class LangfuseUsageReporter(UsageReporterPort):
    def __init__(self, public_key: str, secret_key: str, host: str = DEFAULT_HOST,
                 prices: Optional[Dict[str, Tuple[float, float]]] = None, background: bool = True) -> None:
        self.url = host.rstrip("/") + "/api/public/otel/v1/traces"
        token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        self.headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json",
                        "x-langfuse-ingestion-version": "4"}
        self.prices = load_prices() if prices is None else prices
        self.root_spans: Dict[str, str] = {}
        self.queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        if background:
            threading.Thread(target=self._worker, name="langfuse-usage", daemon=True).start()

    @classmethod
    def from_env(cls) -> Optional["LangfuseUsageReporter"]:
        public, secret = os.environ.get("LANGFUSE_PUBLIC_KEY", ""), os.environ.get("LANGFUSE_SECRET_KEY", "")
        if not public or not secret:
            return None
        return cls(public, secret, os.environ.get("LANGFUSE_HOST", "") or DEFAULT_HOST)

    def report(self, record: RequestRecord, trace_id: str, session_id: str, details: Optional[CallDetails] = None) -> None:
        try:
            self.queue.put(self.payload(record, trace_id, session_id, details))
        except Exception:
            logger.exception("Could not queue the usage of an LLM call")

    def payload(self, record: RequestRecord, trace_id: str, session_id: str,
                details: Optional[CallDetails] = None) -> Dict[str, Any]:
        """The OTLP body of one call: the root span of its message (first call only) and the generation."""
        otel_trace = _hex_id(trace_id, 32)
        details = details or CallDetails()
        trace_name = _trace_name(details.message)
        now = time.time_ns()
        started = details.started_ns or now
        ended = details.ended_ns or started
        spans: List[Dict[str, Any]] = []

        if trace_id not in self.root_spans:
            self.root_spans[trace_id] = _hex_id(uuid.uuid4().hex, 16)
            now = started                              # the message starts with its first call
            root = {
                "langfuse.observation.type": "span",
                "langfuse.trace.name": trace_name,
                "langfuse.session.id": session_id,
            }
            if details.message:
                root["langfuse.trace.input"] = details.message
                root["langfuse.observation.input"] = details.message
            spans.append(_span(otel_trace, self.root_spans[trace_id], "", trace_name, now, now, root))

        billed = billed_output_tokens(record.prompt_tokens, record.completion_tokens, record.total_tokens)
        attributes: Dict[str, Any] = {
            "langfuse.observation.type": "generation",
            "langfuse.session.id": session_id,
            "gen_ai.request.model": record.model,
            "langfuse.observation.model.name": record.model,
            "langfuse.observation.usage_details": json.dumps(
                {"input": record.prompt_tokens, "output": billed, "total": record.prompt_tokens + billed}),
            "langfuse.observation.metadata.phase_id": str(record.phase_id),
            "langfuse.observation.metadata.answered_tokens": str(record.completion_tokens),
            "langfuse.observation.metadata.thinking_tokens": str(
                max(0, record.total_tokens - record.prompt_tokens - record.completion_tokens)),
        }
        if details.input_text is not None:
            attributes["langfuse.observation.input"] = details.input_text
        if details.output_text is not None:
            attributes["langfuse.observation.output"] = details.output_text
        if record.action_id:
            attributes["langfuse.observation.metadata.action_id"] = record.action_id
        cost = cost_usd(self.prices, record.model, record.prompt_tokens, record.completion_tokens, record.total_tokens)
        if cost is not None:
            attributes["langfuse.observation.cost_details"] = json.dumps({"total": cost})

        name = record.phase_name + (f" ({record.action_id})" if record.action_id else "")
        spans.append(_span(otel_trace, _hex_id(record.request_id, 16), self.root_spans[trace_id], name, started, ended, attributes))

        return {"resourceSpans": [{
            "resource": {"attributes": [_attribute("service.name", SERVICE_NAME)]},
            "scopeSpans": [{"scope": {"name": SERVICE_NAME}, "spans": spans}],
        }]}

    def send(self, payload: Dict[str, Any]) -> None:
        request = urllib.request.Request(self.url, data=json.dumps(payload).encode(), headers=self.headers, method="POST")
        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.loads(response.read() or b"{}")
        rejected = (result.get("partialSuccess") or {}).get("rejectedSpans")
        if rejected:
            logger.warning("Langfuse refused part of a usage report", rejected_spans=rejected)

    def _worker(self) -> None:
        while True:
            payload = self.queue.get()
            try:
                self.send(payload)
            except Exception as error:
                logger.warning("Could not send the usage to Langfuse", error_type=type(error).__name__)
            finally:
                self.queue.task_done()

    def flush(self, timeout: float = 15.0) -> bool:
        """Waits until everything queued was sent (for scripts that end right after a run)."""
        done = threading.Event()
        threading.Thread(target=lambda: (self.queue.join(), done.set()), daemon=True).start()
        return done.wait(timeout)


def _trace_name(message: str) -> str:
    """The name of a trace is what the user asked, on one line and not too long to group and read."""
    text = " ".join(message.split())
    return (text[:MAX_NAME_CHARS - 1] + "…") if len(text) > MAX_NAME_CHARS else (text or "user message")


def _hex_id(value: str, length: int) -> str:
    """OpenTelemetry ids are lowercase hex of a fixed size; any text is mapped to one, the same text to the same id."""
    text = str(value).replace("-", "").lower()
    if len(text) == length and all(c in "0123456789abcdef" for c in text):
        return text
    return hashlib.sha256(str(value).encode()).hexdigest()[:length]


def _attribute(key: str, value: Any) -> Dict[str, Any]:
    return {"key": key, "value": {"stringValue": str(value)}}


def _span(trace_id: str, span_id: str, parent_id: str, name: str, start: int, end: int,
          attributes: Dict[str, Any]) -> Dict[str, Any]:
    span: Dict[str, Any] = {
        "traceId": trace_id, "spanId": span_id, "name": name, "kind": 1,
        "startTimeUnixNano": str(start), "endTimeUnixNano": str(end),
        "attributes": [_attribute(k, v) for k, v in attributes.items()],
    }
    if parent_id:
        span["parentSpanId"] = parent_id
    return span
