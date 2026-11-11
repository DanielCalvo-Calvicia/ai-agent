"""Follows the jobs of a tool answer to their result (ADR-018, T-07.4).

The generic part: it knows no protocol, only the interface of job_protocol.py, and it makes no call itself. The caller gives it
`read` (calls the server's read tool), `cancel` (calls its cancel tool, if the server file names one), `left` (the seconds the
message may still wait for its tools) and `sleep`, so a test runs with no real time. Nothing here logs; the caller does, and no
argument or answer ever goes into a log line.

All or nothing (Q10-9): an answer with several jobs gives its tables only when every job ended. If the time is spent, the jobs
still running are cancelled and no table is given.
"""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from infrastructure.outbound.mcp.job_protocol import DONE, UNKNOWN, JobProtocol, JobRef

# The wait between two reads of a job: starts at the first value, doubles, never passes the second (measured in T-07.9).
RECALL_FIRST_WAIT_SECONDS = 3.0   # a tool that is called again, not read (job_recall_tools): the service says to ask again after 3 s
FIRST_WAIT_SECONDS = 1.0
MAX_WAIT_SECONDS = 5.0
CANCEL_LIMIT_SECONDS = 3.0       # a cancel is best effort and has a short limit of its own, even when the budget is spent

# How a followed answer ends (more TOOL_OUTCOMES of mcp_ports.py)
JOB_DONE, JOB_RUNNING, JOB_CANCELLED, JOB_UNKNOWN_SHAPE = "job_done", "job_running", "job_cancelled", "job_unknown_shape"

STILL_RUNNING_TEXT = ("The query is still running and did not finish in the time available, so no data was read. "
                      "Tell the user that it is still running; do not make up any data.")
UNKNOWN_SHAPE_TEXT = "error (internal): the query was started, but the answer that should hold its result could not be understood."

Answer = Dict[str, Any]                                                     # {"result": text, "is_error": False} or {"error": text, "is_error": True}
Read = Callable[[Dict[str, Any], Optional[float]], Awaitable[Tuple[Answer, str]]]     # (arguments, seconds left) -> (answer, how the call ended)
Cancel = Callable[[Dict[str, Any], float], Awaitable[None]]                  # (arguments, limit); best effort
Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class FollowUp:
    answer: Answer
    outcome: str        # JOB_DONE, JOB_RUNNING, JOB_CANCELLED, JOB_UNKNOWN_SHAPE, or the outcome of a read that failed
    reads: int          # how many reads were made


async def follow_up(protocol: JobProtocol, answer_text: str, jobs: List[JobRef], read: Read, cancel: Optional[Cancel],
                    left: Callable[[], Optional[float]], sleep: Sleep, first_wait: float = 0.0) -> FollowUp:
    finished: Dict[int, str] = {}
    reads, wait = 0, FIRST_WAIT_SECONDS
    if first_wait > 0:                    # the first read is at once, unless the caller says to wait (the tool is called again)
        remaining = left()
        pause = first_wait if remaining is None else min(first_wait, remaining)
        if pause > 0:
            await sleep(pause)
    while True:
        for index, job in enumerate(jobs):
            if index in finished:
                continue
            if not job.job_id:         # the protocol saw a job but could not read its id: nothing can be read or cancelled
                await _cancel_running(jobs, finished | {index: ""}, protocol, cancel)
                return FollowUp({"error": UNKNOWN_SHAPE_TEXT, "is_error": True}, JOB_UNKNOWN_SHAPE, reads)
            remaining = left()
            if remaining is not None and remaining <= 0:
                return await _give_up(jobs, finished, protocol, cancel, reads)
            answer, outcome = await read(protocol.read_arguments(job), remaining)
            reads += 1
            if answer["is_error"]:
                await _cancel_running(jobs, finished | {index: ""}, protocol, cancel)     # the job that could not be read is not cancelled
                return FollowUp(answer, outcome, reads)
            state = protocol.state(answer["result"])
            if state == DONE:
                finished[index] = answer["result"]
            elif state == UNKNOWN:
                await _cancel_running(jobs, finished, protocol, cancel)      # this job may still run: stop it too
                return FollowUp({"error": UNKNOWN_SHAPE_TEXT, "is_error": True}, JOB_UNKNOWN_SHAPE, reads)
        if len(finished) == len(jobs):
            merged = protocol.merge(answer_text, [finished[i] for i in range(len(jobs))])
            return FollowUp({"result": merged, "is_error": False}, JOB_DONE, reads)
        remaining = left()
        pause = wait if remaining is None else min(wait, remaining)
        if pause <= 0:
            return await _give_up(jobs, finished, protocol, cancel, reads)
        await sleep(pause)
        wait = min(wait * 2, MAX_WAIT_SECONDS)


async def _give_up(jobs: List[JobRef], finished: Dict[int, str], protocol: JobProtocol, cancel: Optional[Cancel], reads: int) -> FollowUp:
    """The time is spent: stop the jobs that still run and give back the plain "still running" answer, never an empty one."""
    cancelled = await _cancel_running(jobs, finished, protocol, cancel)
    return FollowUp({"result": STILL_RUNNING_TEXT, "is_error": False}, JOB_CANCELLED if cancelled else JOB_RUNNING, reads)


async def _cancel_running(jobs: List[JobRef], finished: Dict[int, str], protocol: JobProtocol, cancel: Optional[Cancel]) -> bool:
    """Cancels every job that did not finish; True when at least one cancel was sent. A cancel that fails is not an error."""
    if cancel is None:
        return False
    sent = False
    for index, job in enumerate(jobs):
        if index in finished:
            continue
        try:
            await cancel(protocol.cancel_arguments(job), CANCEL_LIMIT_SECONDS)
            sent = True
        except Exception:
            pass
    return sent
