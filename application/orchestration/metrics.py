# ===============================================
#  METRICS
#  Token accounting for one agent flow.
# ===============================================

import threading
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from application.outbound.ports.usage_ports import UsageReporterPort

PHASE_NAMES: Dict[int, str] = {
    1:  "triage_specialist",
    2:  "project_manager",
    3:  "safety_quality_gatekeeper",
    4:  "cognitive_worker",
    5:  "mcp_operator",
    6:  "data_engineer",
    7:  "draft_writer",
    8:  "editor_in_chief",
    9:  "answer_checker",
    99: "user_clarification",
}


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
        e.g. metrics.by_phase["cognitive_worker"]["gpt-4.1"].total

    by_model : Dict[model, TokenCount]
        Cross-phase token aggregation per model.
        e.g. metrics.by_model["gpt-4.1"].total

    totals : TokenCount
        Grand total across the entire session.
    """

    def __init__(self, reporter: Optional["UsageReporterPort"] = None) -> None:
        self.reporter = reporter
        self._lock = threading.Lock()                    # actions can run at the same time
        self.trace_id = uuid.uuid4().hex
        self.session_id = ""
        self.user_message = ""
        self.request_log: List[RequestRecord] = []
        self.by_phase:    Dict[str, Dict[str, TokenCount]] = {}
        self.by_model:    Dict[str, TokenCount] = {}
        self.totals:      TokenCount = TokenCount()

    # ------------------------------------------

    def begin_message(self, trace_id: Optional[str], session_id: str, message: str = "") -> None:
        """Names the user message the next calls belong to (the trace of the usage report)."""
        self.trace_id = str(trace_id) if trace_id else uuid.uuid4().hex
        self.session_id = session_id
        self.user_message = message

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
        phase_name = PHASE_NAMES.get(phase_id, f"phase_{phase_id}")
        request_id = uuid.uuid4().hex[:12]

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
        )
        self.request_log.append(entry)

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
                                     CallDetails(self.user_message, input_text, output_text, started_ns, ended_ns))
            except Exception:
                pass                                     # reporting is optional: it never breaks a call

        return request_id

    # ------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Returns a fully serialisable summary dict for logging or inspection."""
        return {
            "total_requests":           self.totals.requests,
            "total_prompt_tokens":      self.totals.prompt,
            "total_completion_tokens":  self.totals.completion,
            "total_tokens":             self.totals.total,
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
        }
