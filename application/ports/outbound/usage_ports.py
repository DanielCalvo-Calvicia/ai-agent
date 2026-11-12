from abc import ABC, abstractmethod
from typing import Optional

from application.dtos.outbound.usage import RequestRecord, CallDetails
from application.dtos.outbound.tools import ToolCallRecord


class UsageReporterPort(ABC):
    """Receives every LLM call of a message (model, tokens, what was sent and answered). Must never raise."""

    @abstractmethod
    def report(self, record: RequestRecord, trace_id: str, session_id: str, details: Optional[CallDetails] = None) -> None:
        raise NotImplementedError

    def report_tool_call(self, call: ToolCallRecord, trace_id: str, session_id: str, details: Optional[CallDetails] = None) -> None:
        """One MCP tool call: tool, outcome, duration; never an argument or an answer. Optional: ignored by default."""
        return None
