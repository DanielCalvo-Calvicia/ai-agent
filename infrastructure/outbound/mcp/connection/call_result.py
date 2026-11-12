"""What one MCP call came to: the answer dict, why it failed, how it ended. Plain functions on text and exceptions (no network, no log).

An answer is `{"result": text, "is_error": False}` or `{"error": text, "is_error": True}`. The text of a transport error can hold
the address of the server, so an error is described by its class names (`error_types`), never by its text.
"""

import re
from typing import Any, Dict, Optional

import httpx

# `error (<kind>): <message>` is how dynamics_microservice reports a failed tool. Only `retry_later` is worth one more try.
_ERROR_KIND = re.compile(r"error \((\w+)\)")
RETRYABLE_KINDS = ("retry_later",)
TOOL_ERROR_KINDS = ("input", "not_found", "retry_later", "source_problem", "internal")   # what a tool may say; the rest of TOOL_OUTCOMES is ours


def success(text: str) -> Dict[str, Any]:
    return {"result": text, "is_error": False}


def failure(text: str) -> Dict[str, Any]:
    return {"error": text, "is_error": True}


def error_kind(text: str) -> Optional[str]:
    """The `<kind>` of an `error (<kind>): ...` text, or None."""
    match = _ERROR_KIND.search(text)
    return match.group(1) if match else None


def is_timeout(error: BaseException) -> bool:
    """A timeout, alone or as the only kind of error inside the exception groups the MCP clients raise."""
    if isinstance(error, BaseExceptionGroup):
        return all(is_timeout(inner) for inner in error.exceptions)
    return isinstance(error, (TimeoutError, httpx.TimeoutException))


def error_types(error: BaseException) -> str:
    """The class names of an error (inside the exception groups the MCP clients raise).
    Used instead of its text or traceback, which can hold the address of the server."""
    if isinstance(error, BaseExceptionGroup):
        return ",".join(sorted({error_types(inner) for inner in error.exceptions}))
    return type(error).__name__


def content_as_text(item: Any) -> str:
    """The text of one content item of a tool result (`str()` of an item that is not text)."""
    return item.text if hasattr(item, 'text') and 'text' in item.__dict__ else str(item)
