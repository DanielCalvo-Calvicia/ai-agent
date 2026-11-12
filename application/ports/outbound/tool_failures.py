from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, List, Optional

from application.dtos.outbound.tools import ToolCallRecord


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
