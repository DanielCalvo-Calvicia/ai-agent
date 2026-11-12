import time

import anyio
from typing import Any, Dict, List, Optional, Tuple

from application.ports.outbound.mcp_ports import McpToolsPort
from application.dtos.outbound.tools import ToolCallRecord, ToolScope, ToolDefinition
from application.ports.outbound.tool_wait_budget import remaining_tool_wait, spend_tool_wait
from application.ports.outbound.tool_failures import report_final_tool_failure, report_tool_call
from infrastructure.outbound.mcp.connection.call_result import (
    RETRYABLE_KINDS, TOOL_ERROR_KINDS, content_as_text, error_kind, failure, is_timeout, success,
)
from infrastructure.outbound.mcp.connection.client_manager import MCPClientManager
from infrastructure.outbound.mcp.jobs.follow_up import JOB_UNKNOWN_SHAPE, RECALL_FIRST_WAIT_SECONDS, FollowUp, follow_up
from infrastructure.outbound.mcp.jobs.protocol import NO_JOBS, JobProtocol, JobRef
from infrastructure.outbound.mcp.jobs.registry import get_protocol
from infrastructure.outbound.mcp.connection.limits import call_timeout_seconds
from infrastructure.outbound.mcp.execution.masking import mask_personal_columns, masking_enabled
from infrastructure.outbound.mcp.server import McpServer
from infrastructure.outbound.mcp.catalog.tool_catalog import MCPToolCatalog
from shared_logging import get_logger

logger = get_logger(__name__)

Answer = Dict[str, Any]


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
        self._clock = time.monotonic       # the follow-up of a job reads these two, so a test can run it with no real time
        self._sleep = anyio.sleep

    # -- the port --------------------------------------------------------------------------------------------------------

    def list_tools(self, server_name: str) -> List[ToolDefinition]:
        return self.catalog.list_tools(server_name)

    def call_tool(self, tool_name: str, arguments: Dict[str, Any], scope: Optional[ToolScope] = None) -> Dict[str, Any]:
        """What the direct call of an action uses (T-08.3): the same as `execute`, by the name of the port."""
        return self.execute(tool_name, arguments, scope)

    def execute(self, tool_name: str, args: Dict[str, Any], scope: Optional[ToolScope] = None) -> Dict[str, Any]:
        """`scope`: the tools the step that asks may use (T-05.13); a tool outside it is refused and no server is called."""
        started_ns, started = time.time_ns(), time.monotonic()
        answer, outcome, attempts = anyio.run(self._execute_async, tool_name, args, scope)
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

    # -- one call: refuse, call (with one retry), follow a job ------------------------------------------------------------

    async def _execute_async(self, tool_name: str, args: Dict[str, Any], scope: Optional[ToolScope] = None) -> Tuple[Answer, str, int]:
        """The answer, how the call ended (one of TOOL_OUTCOMES) and how many tries it took."""
        server_name = await self.catalog.server_of(tool_name)
        refused = _refusal(server_name, tool_name, scope)
        if refused:
            return refused, "not_found", 0

        # The message may wait only so long for its tools in total (the budget the action loop sets): a call gets what is left.
        left, begun = remaining_tool_wait(), time.monotonic()
        answer, outcome, attempts = await self._call_with_retry(server_name, tool_name, args, left, begun)
        if answer["is_error"]:
            return answer, outcome, attempts

        server = McpServer.find(getattr(self.client_manager, "configs", None), server_name)
        protocol = _protocol_of(server)
        jobs = protocol.detect(answer["result"])
        if not (jobs and server and server.job_read_tool):
            return answer, outcome, attempts
        recall = (tool_name, args) if tool_name in server.job_recall_tools else None
        left_now = None if left is None else left - (time.monotonic() - begun)     # what is left after the first call
        followed = await self._follow_jobs(server, protocol, answer["result"], jobs, left_now, recall)
        return followed.answer, followed.outcome, attempts + followed.reads

    async def _call_with_retry(self, server_name: str, tool_name: str, args: Dict[str, Any], left: Optional[float],
                               begun: float) -> Tuple[Answer, str, int]:
        """The first try and, only after a transport error or `retry_later`, one more, each cut to what the message may still wait."""
        limit = _limit(left, begun)
        if limit <= 0:
            return failure("No wait is left for tool calls in this message, so the tool was not called."), "timeout", 0
        answer, retry_reason, outcome = await self._call(server_name, tool_name, args, limit)
        if not retry_reason:
            return answer, outcome, 1
        limit = _limit(left, begun)
        if limit <= 0:
            return answer, outcome, 1
        logger.warning("MCP call failed, trying once more", tool_name=tool_name, reason=retry_reason)
        answer, _, outcome = await self._call(server_name, tool_name, args, limit)
        return answer, outcome, 2

    async def _call(self, server_name: str, tool_name: str, args: Dict[str, Any], limit: float) -> Tuple[Answer, Optional[str], str]:
        """One try. Returns the answer, why one more try may help (`transport` or `retry_later`, else None) and how it ended."""
        try:
            with anyio.fail_after(limit):
                async with self.client_manager.session_scope(server_name) as session:
                    result = await session.call_tool(tool_name, arguments=args)
        except Exception as error:
            if is_timeout(error):
                return failure(f"MCP call timed out after {limit:g} seconds."), None, "timeout"
            if isinstance(error, ValueError):
                return failure(f"MCP configuration error: {error}"), None, "internal"
            # The text of a transport error can hold the address of the server: keep it out of the answer.
            return failure("MCP transport error: the server could not be reached or the connection broke."), "transport", "transport"

        text = "\n".join(content_as_text(item) for item in result.content)
        if result.isError:
            kind = error_kind(text)
            return failure(text), (kind if kind in RETRYABLE_KINDS else None), kind if kind in TOOL_ERROR_KINDS else "internal"

        # Personal columns (customer name, e-mail, phone, address...) are hidden before any model sees the answer (masking.py).
        return success(mask_personal_columns(text) if masking_enabled() else text), None, "ok"

    # -- the follow-up of a job ------------------------------------------------------------------------------------------

    async def _follow_jobs(self, server: McpServer, protocol: JobProtocol, answer_text: str, jobs: List[JobRef],
                           left_now: Optional[float], recall: Optional[Tuple[str, Dict[str, Any]]] = None) -> FollowUp:
        """Reads the jobs of an answer to their result (jobs/follow_up.py), inside what the message may still wait (`left_now`
        seconds). Only the read tool and the cancel tool the server file names are called, only with the ids the protocol found
        in the answer.

        `recall` is (tool, arguments) for a tool of `job_recall_tools`: its job is only one query of a composed answer, so reading
        it would give the rows of that query and not the answer. The same tool is called again with the same arguments instead
        (the service says to ask again after `retry_after_seconds`); nothing the model or an answer says is ever called."""
        started = self._clock()

        def time_left() -> Optional[float]:
            return None if left_now is None else left_now - (self._clock() - started)

        async def read(arguments: Dict[str, Any], remaining: Optional[float]) -> Tuple[Answer, str]:
            limit = call_timeout_seconds() if remaining is None else min(call_timeout_seconds(), remaining)
            tool, tool_arguments = recall if recall is not None else (server.job_read_tool, arguments)
            result, _, outcome = await self._call(server.name, tool, tool_arguments, limit)
            return result, outcome

        async def cancel(arguments: Dict[str, Any], limit: float) -> None:
            await self._call(server.name, server.job_cancel_tool, arguments, limit)

        followed = await follow_up(protocol, answer_text, jobs, read, cancel if server.job_cancel_tool else None, time_left, self._sleep,
                                   RECALL_FIRST_WAIT_SECONDS if recall is not None else 0.0)
        if followed.outcome == JOB_UNKNOWN_SHAPE:
            logger.warning("MCP job answer not understood", server_name=server.name, protocol=protocol.name)
        return followed


def _refusal(server_name: Optional[str], tool_name: str, scope: Optional[ToolScope]) -> Optional[Answer]:
    """The answer for a call that must not go out (no server offers the tool, or the step may not use it); None when it may."""
    if not server_name:
        return failure(f"Tool '{tool_name}' not found on any registered MCP server.")
    if scope is not None and not scope.allows(server_name, tool_name):
        return failure(f"Tool '{tool_name}' is not allowed for this step.")
    return None


def _limit(left: Optional[float], begun: float) -> float:
    """The call limit, cut to what the message may still wait (`left` seconds when the call began)."""
    limit = call_timeout_seconds()
    return limit if left is None else min(limit, left - (time.monotonic() - begun))


def _protocol_of(server: Optional[McpServer]) -> JobProtocol:
    """The job protocol the server file declares; `none` without the field or without a server (the config loader refuses a name
    it does not know, so an unknown one here is `none`)."""
    try:
        return get_protocol(server.job_protocol if server else NO_JOBS)
    except ValueError:
        return get_protocol(NO_JOBS)
