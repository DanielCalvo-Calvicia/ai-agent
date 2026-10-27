from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from application.orchestration.support.metrics import RequestRecord


@dataclass(frozen=True)
class CallDetails:
    """What went in and out of one LLM call, and what the user asked in the message it belongs to."""
    message: str = ""
    input_text: Optional[str] = None
    output_text: Optional[str] = None
    started_ns: Optional[int] = None     # wall clock of the first attempt (time.time_ns)
    ended_ns: Optional[int] = None        # wall clock of the answer that was used


class UsageReporterPort(ABC):
    """Receives every LLM call of a message (model, tokens, what was sent and answered). Must never raise."""

    @abstractmethod
    def report(self, record: RequestRecord, trace_id: str, session_id: str, details: Optional[CallDetails] = None) -> None:
        raise NotImplementedError
