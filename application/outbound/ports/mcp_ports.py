import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional

from domain.value_objects.llm_request.tool import ToolDefinition


class McpToolsPort(ABC):
    """What the agent needs to know about MCP servers: which tools each one offers."""

    @abstractmethod
    def list_tools(self, server_name: str) -> List[ToolDefinition]:
        raise NotImplementedError


# How a tool call ended. A tool error is read from `error (<kind>): ...`; anything else is `internal`.
TOOL_OUTCOMES = ("ok", "timeout", "input", "not_found", "retry_later", "source_problem", "internal", "transport")


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


class ToolFailures:
    """What one attempt of an MCP step learned about its tool calls: did one end in a failure that asking again cannot fix,
    and which calls were made."""

    def __init__(self) -> None:
        self.final = False
        self.calls: List[ToolCallRecord] = []


_watching: ContextVar[Optional[ToolFailures]] = ContextVar("mcp_tool_failures", default=None)


@contextmanager
def watch_tool_failures() -> Iterator[ToolFailures]:
    """The step loop wraps one attempt in this; the MCP adapter reports into it (same thread, same context)."""
    failures = ToolFailures()
    token = _watching.set(failures)
    try:
        yield failures
    finally:
        _watching.reset(token)


def report_final_tool_failure() -> None:
    """Called by the MCP adapter when a tool call failed for good (its own retry, if it deserved one, is spent).
    Nothing happens when no step is watching."""
    failures = _watching.get()
    if failures is not None:
        failures.final = True


def report_tool_call(call: ToolCallRecord) -> None:
    """Called by the MCP adapter after every tool call. The step that is watching collects it (and hands it to the
    metrics). Nothing happens when no step is watching."""
    failures = _watching.get()
    if failures is not None:
        failures.calls.append(call)


class ToolWaitBudget:
    """How long the tool calls of one message may wait in total (the sum of their durations)."""

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self._spent = 0.0
        self._lock = threading.Lock()

    def remaining(self) -> float:
        with self._lock:
            return max(0.0, self.seconds - self._spent)

    def spend(self, seconds: float) -> None:
        with self._lock:
            self._spent += max(0.0, seconds)


_budget: ContextVar[Optional[ToolWaitBudget]] = ContextVar("mcp_tool_wait_budget", default=None)


@contextmanager
def tool_wait_budget(seconds: float) -> Iterator[ToolWaitBudget]:
    """The action loop wraps the run of one message in this; the MCP adapter spends from it and never waits past it."""
    budget = ToolWaitBudget(seconds)
    token = _budget.set(budget)
    try:
        yield budget
    finally:
        _budget.reset(token)


def remaining_tool_wait() -> Optional[float]:
    """Seconds the tool calls of this message may still wait; None when no budget is set (no limit)."""
    budget = _budget.get()
    return None if budget is None else budget.remaining()


def spend_tool_wait(seconds: float) -> None:
    budget = _budget.get()
    if budget is not None:
        budget.spend(seconds)
