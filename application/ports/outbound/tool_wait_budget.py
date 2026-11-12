import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional


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
