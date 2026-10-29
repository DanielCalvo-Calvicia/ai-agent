import re
import time

import anyio
import httpx
from typing import Any, Dict, List, Optional, Tuple

from application.outbound.ports.mcp_ports import (
    McpToolsPort,
    ToolCallRecord,
    remaining_tool_wait,
    report_final_tool_failure,
    report_tool_call,
    spend_tool_wait,
)
from domain.value_objects.llm_request.tool import ToolDefinition
from infrastructure.outbound.mcp.client_manager import MCPClientManager
from infrastructure.outbound.mcp.masking import mask_personal_columns, masking_enabled
from infrastructure.outbound.mcp.tool_catalog import MCPToolCatalog, call_timeout_seconds
from shared_logging import get_logger

logger = get_logger(__name__)

# `error (<kind>): <message>` is how dynamics_microservice reports a failed tool. Only `retry_later` is worth one more try.
_ERROR_KIND = re.compile(r"error \((\w+)\)")
RETRYABLE_KINDS = ("retry_later",)
TOOL_ERROR_KINDS = ("input", "not_found", "retry_later", "source_problem", "internal")   # what a tool may say; the rest of TOOL_OUTCOMES is ours


class MCPToolExecutor(McpToolsPort):
    """
    What the LLM adapter uses for MCP: `list_tools` to offer the tools of a server and
    `execute` to run one. Synchronous, so call it from a worker thread.

    A call is tried once more (once) only after a transport error or `error (retry_later)`. A timeout and every other
    tool error is final. Each call is measured (tool, outcome, duration) and logged; nothing here logs, measures or
    reports an argument or an answer.
    """

    def __init__(self, client_manager: MCPClientManager, catalog: Optional[MCPToolCatalog] = None):
        self.client_manager = client_manager
        self.catalog = catalog or MCPToolCatalog(client_manager)

    def list_tools(self, server_name: str) -> List[ToolDefinition]:
        return self.catalog.list_tools(server_name)

    def execute(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        started_ns, started = time.time_ns(), time.monotonic()
        answer, outcome, attempts = anyio.run(self._execute_async, tool_name, args)
        spend_tool_wait(time.monotonic() - started)       # what this message may still wait for tools shrinks
        self._report(ToolCallRecord(tool_name, outcome, round((time.monotonic() - started) * 1000), attempts,
                                    started_ns, time.time_ns()))
        if answer["is_error"]:
            # the retry that this failure deserved (if any) is already spent: tell the step that asking again cannot help
            report_final_tool_failure()
        return answer

    @staticmethod
    def _report(call: ToolCallRecord) -> None:
        logger.info("MCP tool call", tool_name=call.tool, outcome=call.outcome, duration_ms=call.duration_ms, attempts=call.attempts)
        report_tool_call(call)

    async def _execute_async(self, tool_name: str, args: Dict[str, Any]) -> Tuple[Dict[str, Any], str, int]:
        """The answer, how the call ended (one of TOOL_OUTCOMES) and how many tries it took."""
        server_name = await self.catalog.server_of(tool_name)
        if not server_name:
            return {"error": f"Tool '{tool_name}' not found on any registered MCP server.", "is_error": True}, "not_found", 0

        # The message may wait only so long for its tools in total (the budget the action loop sets): a call gets what is left.
        left, begun = remaining_tool_wait(), time.monotonic()
        limit = self._limit(left, begun)
        if limit <= 0:
            return {"error": "No wait is left for tool calls in this message, so the tool was not called.", "is_error": True}, "timeout", 0
        answer, retry_reason, outcome = await self._call(server_name, tool_name, args, limit)
        if retry_reason:
            limit = self._limit(left, begun)
            if limit > 0:
                logger.warning("MCP call failed, trying once more", tool_name=tool_name, reason=retry_reason)
                answer, _, outcome = await self._call(server_name, tool_name, args, limit)
                return answer, outcome, 2
        return answer, outcome, 1

    @staticmethod
    def _limit(left: Optional[float], begun: float) -> float:
        """The call limit, cut to what the message may still wait (`left` seconds when the call began)."""
        limit = call_timeout_seconds()
        return limit if left is None else min(limit, left - (time.monotonic() - begun))

    async def _call(self, server_name: str, tool_name: str, args: Dict[str, Any], limit: float) -> Tuple[Dict[str, Any], Optional[str], str]:
        """One try. Returns the answer, why one more try may help (`transport` or `retry_later`, else None) and how it ended."""
        try:
            with anyio.fail_after(limit):
                async with self.client_manager.session_scope(server_name) as session:
                    result = await session.call_tool(tool_name, arguments=args)
        except Exception as error:
            if _is_timeout(error):
                return {"error": f"MCP call timed out after {limit:g} seconds.", "is_error": True}, None, "timeout"
            if isinstance(error, ValueError):
                return {"error": f"MCP configuration error: {error}", "is_error": True}, None, "internal"
            # The text of a transport error can hold the address of the server: keep it out of the answer.
            return {"error": "MCP transport error: the server could not be reached or the connection broke.", "is_error": True}, "transport", "transport"

        text = "\n".join(_content_as_text(item) for item in result.content)
        if result.isError:
            kind = _error_kind(text)
            return {"error": text, "is_error": True}, (kind if kind in RETRYABLE_KINDS else None), kind if kind in TOOL_ERROR_KINDS else "internal"

        # Personal columns (customer name, e-mail, phone, address...) are hidden before any model sees the answer (masking.py).
        return {"result": mask_personal_columns(text) if masking_enabled() else text, "is_error": False}, None, "ok"


def _error_kind(text: str) -> Optional[str]:
    match = _ERROR_KIND.search(text)
    return match.group(1) if match else None


def _is_timeout(error: BaseException) -> bool:
    """A timeout, alone or as the only kind of error inside the exception groups the MCP clients raise."""
    if isinstance(error, BaseExceptionGroup):
        return all(_is_timeout(inner) for inner in error.exceptions)
    return isinstance(error, (TimeoutError, httpx.TimeoutException))


def _content_as_text(item: Any) -> str:
    return item.text if hasattr(item, 'text') and 'text' in item.__dict__ else str(item)
