from dataclasses import dataclass
from typing import Any, Dict


# How a tool call ended. A tool error is read from `error (<kind>): ...`; anything else is `internal`. The `job_*` ones are
# the end of an answer that held a job (ADR-018): read to its result, still running when the time was spent (with or without
# a cancel sent), or an answer the job protocol did not understand.
TOOL_OUTCOMES = ("ok", "timeout", "input", "not_found", "retry_later", "source_problem", "internal", "transport",
                 "job_done", "job_running", "job_cancelled", "job_unknown_shape")


@dataclass(frozen=True)
class ToolCallRecord:
    """One tool call, as the metrics and the usage report see it. Never the arguments or the answer."""
    tool: str
    outcome: str                  # one of TOOL_OUTCOMES
    duration_ms: int              # the whole call, its retry included
    attempts: int = 1             # 0: no call was made (no server offers the tool); 2: it was retried
    started_ns: int = 0           # wall clock (time.time_ns)
    ended_ns: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {"tool": self.tool, "outcome": self.outcome, "duration_ms": self.duration_ms, "attempts": self.attempts}
