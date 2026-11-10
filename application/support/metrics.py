# ===============================================
#  METRICS
#  Token accounting for one agent flow. One record per LLM call, with the profile, the flow, the step, the model, the client,
#  the tokens, the cost and the hash of the assembled profile (T-05.15); the totals by any of those keys come from the records.
#  No record holds a token of a client, an `inputs` value, a tool argument or a tool answer.
# ===============================================

import threading
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from application.steps.catalog import CONVERSATION_PHASES, PHASES
from application.outbound.ports.mcp_ports import ToolCallRecord
from shared_logging import get_logger

if TYPE_CHECKING:
    from application.outbound.ports.usage_ports import UsageReporterPort

logger = get_logger(__name__)

# The keys a record can be totalled by (`SessionMetrics.total_by`); `step` is the step name, `phase_id` stays beside it as a label (Q07-9).
RECORD_KEYS = ("profile", "flow", "step", "model", "client")

# model, prompt tokens, completion tokens, total tokens -> USD, or None when the model has no price (composition root)
CostOf = Callable[[str, int, int, int], Optional[float]]

# phase id -> step name, read from the constants of each phase file (application/steps).
# PHASE_NAMES covers the text flows (identification, conversation, special: what the cost and budget tables are about); ALL_PHASE_NAMES every flow.
PHASE_NAMES: Dict[int, str] = {phase_id: info.step_name for phase_id, info in CONVERSATION_PHASES.items()}
ALL_PHASE_NAMES: Dict[int, str] = {phase_id: info.step_name for phase_id, info in PHASES.items()}


@dataclass
class TokenCount:
    """Accumulated token counts plus a request counter."""
    prompt: int = 0
    completion: int = 0
    total: int = 0
    requests: int = 0

    def add(self, prompt: int, completion: int, total: int) -> None:
        self.prompt += prompt
        self.completion += completion
        self.total += total
        self.requests += 1

    def to_dict(self) -> Dict[str, int]:
        return {
            "prompt": self.prompt,
            "completion": self.completion,
            "total": self.total,
            "requests": self.requests,
        }


@dataclass
class RequestRecord:
    """Immutable snapshot of a single LLM call."""
    request_id: str
    phase_id: int
    phase_name: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    action_id: Optional[str] = None
    profile: str = ""
    flow: str = ""
    client: str = ""
    profile_hash: str = ""            # SHA-256 (hex) of the assembled profile, without its token hash
    cost_usd: Optional[float] = None  # None: the model has no price in config/

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id":       self.request_id,
            "phase_id":         self.phase_id,
            "phase_name":       self.phase_name,
            "model":            self.model,
            "prompt_tokens":    self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens":     self.total_tokens,
            "action_id":        self.action_id,
            "profile":          self.profile,
            "flow":             self.flow,
            "step":             self.phase_name,
            "client":           self.client,
            "profile_hash":     self.profile_hash,
            "cost_usd":         self.cost_usd,
        }


class SessionMetrics:
    """
    Full observability for one agent session.

    Attributes
    ----------
    request_log : List[RequestRecord]
        Ordered log of every LLM call made during the session.

    by_phase : Dict[phase_name, Dict[model, TokenCount]]
        Token aggregation grouped first by phase then by model.
        e.g. metrics.by_phase["cognitive_worker"]["gemini-3.6-flash"].total

    by_model : Dict[model, TokenCount]
        Cross-phase token aggregation per model.
        e.g. metrics.by_model["gemini-3.6-flash"].total

    totals : TokenCount
        Grand total across the entire session.
    """

    def __init__(self, reporter: Optional["UsageReporterPort"] = None, cost_of: Optional[CostOf] = None) -> None:
        self.reporter = reporter
        self.cost_of = cost_of                           # the prices come from outside (config/): none, no cost
        self.profile = self.flow = self.client = self.profile_hash = ""     # what the message runs (begin_message)
        self._lock = threading.Lock()                    # actions can run at the same time
        self.trace_id = uuid.uuid4().hex
        self.session_id = ""
        self.user_message = ""
        self.request_log: List[RequestRecord] = []
        self.tool_calls:  List[ToolCallRecord] = []      # the MCP tool calls of the message: tool, outcome, duration, never a value
        self.by_phase:    Dict[str, Dict[str, TokenCount]] = {}
        self.by_model:    Dict[str, TokenCount] = {}
        self.totals:      TokenCount = TokenCount()

    # ------------------------------------------

    def begin_message(self, trace_id: Optional[str], session_id: str, message: str = "", profile: str = "", flow: str = "",
                      client: str = "", profile_hash: str = "") -> None:
        """Names the user message the next calls belong to (the trace of the usage report) and the profile it runs."""
        self.trace_id = str(trace_id) if trace_id else uuid.uuid4().hex
        self.session_id = session_id
        self.user_message = message
        self.profile, self.flow, self.client, self.profile_hash = profile, flow, client, profile_hash

    def record(
        self,
        phase_id:   int,
        model:      str,
        prompt:     int,
        completion: int,
        total:      int,
        action_id:  Optional[str] = None,
        input_text:  Optional[str] = None,
        output_text: Optional[str] = None,
        started_ns: Optional[int] = None,
        ended_ns: Optional[int] = None,
    ) -> str:
        """
        Record one LLM call. Returns the generated request_id.
        Updates by_phase, by_model, and totals in one pass.
        """
        with self._lock:
            return self._record(phase_id, model, prompt, completion, total, action_id,
                                input_text, output_text, started_ns, ended_ns)

    def _record(self, phase_id, model, prompt, completion, total, action_id, input_text, output_text, started_ns, ended_ns) -> str:
        phase_name = ALL_PHASE_NAMES.get(phase_id, f"phase_{phase_id}")
        request_id = uuid.uuid4().hex[:12]
        cost = self.cost_of(model, prompt, completion, total) if self.cost_of else None

        # ---- request log -------------------------------------------
        entry = RequestRecord(
            request_id=request_id,
            phase_id=phase_id,
            phase_name=phase_name,
            model=model,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            action_id=action_id,
            profile=self.profile,
            flow=self.flow,
            client=self.client,
            profile_hash=self.profile_hash,
            cost_usd=cost,
        )
        self.request_log.append(entry)
        # one line per call: which profile, flow, step and model, and how much. Never the text, a token or a tool value.
        logger.info("LLM call", profile=self.profile, flow=self.flow, step=phase_name, phase_id=phase_id, model=model,
                    client=self.client, profile_hash=self.profile_hash[:12], prompt_tokens=prompt, completion_tokens=completion,
                    total_tokens=total, cost_usd=cost)

        # ---- by_phase[phase_name][model] ---------------------------
        phase_bucket = self.by_phase.setdefault(phase_name, {})
        phase_bucket.setdefault(model, TokenCount()).add(prompt, completion, total)

        # ---- by_model[model] ---------------------------------------
        self.by_model.setdefault(model, TokenCount()).add(prompt, completion, total)

        # ---- session totals ----------------------------------------
        self.totals.add(prompt, completion, total)

        if self.reporter is not None:
            try:
                from application.outbound.ports.usage_ports import CallDetails
                self.reporter.report(entry, self.trace_id, self.session_id,
                                     CallDetails(self.user_message, input_text, output_text, started_ns, ended_ns,
                                                 self.profile, self.flow, self.client, self.profile_hash))
            except Exception:
                pass                                     # reporting is optional: it never breaks a call

        return request_id

    def total_by(self, *keys: str) -> Dict[Tuple[str, ...], TokenCount]:
        """The tokens of the message grouped by any of RECORD_KEYS (`total_by("profile", "model")`), from the records."""
        for key in keys:
            if key not in RECORD_KEYS:
                raise ValueError(f"cannot total by {key!r}. Keys: {', '.join(RECORD_KEYS)}")
        groups: Dict[Tuple[str, ...], TokenCount] = {}
        with self._lock:
            for record in self.request_log:
                label = tuple(record.phase_name if key == "step" else getattr(record, key) for key in keys)
                groups.setdefault(label, TokenCount()).add(record.prompt_tokens, record.completion_tokens, record.total_tokens)
        return groups

    def message_cost(self) -> Optional[float]:
        """The cost in USD of every call of the message that has a price; None when no call has one."""
        costs = [r.cost_usd for r in self.request_log if r.cost_usd is not None]
        return sum(costs) if costs else None

    def record_tool_call(self, call: ToolCallRecord) -> None:
        """Records one MCP tool call next to the tokens, and hands it to the usage report (which may fail: it never breaks a call)."""
        with self._lock:
            self.tool_calls.append(call)
            if self.reporter is not None:
                try:
                    from application.outbound.ports.usage_ports import CallDetails
                    self.reporter.report_tool_call(call, self.trace_id, self.session_id,
                                                   CallDetails(self.user_message, None, None, call.started_ns, call.ended_ns,
                                                   self.profile, self.flow, self.client, self.profile_hash))
                except Exception:
                    pass

    # ------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Returns a fully serialisable summary dict for logging or inspection."""
        return {
            "total_requests":           self.totals.requests,
            "total_prompt_tokens":      self.totals.prompt,
            "total_completion_tokens":  self.totals.completion,
            "total_tokens":             self.totals.total,
            "total_cost_usd":           self.message_cost(),
            "by_phase": {
                phase: {
                    model: tc.to_dict()
                    for model, tc in models.items()
                }
                for phase, models in self.by_phase.items()
            },
            "by_model": {
                model: tc.to_dict()
                for model, tc in self.by_model.items()
            },
            "request_log": [
                r.to_dict() for r in self.request_log
            ],
            "tool_calls": [
                c.to_dict() for c in self.tool_calls
            ],
        }
