"""`dynamics_pending`: the shape `dynamics_microservice` answered on 2026-11-11 (T-07.5, ADR-018).

A workflow tool that is not done answers its metadata and, for each table not done, a section like

    ## open_orders (open)
    note: pending: the query is still running as job <id> (running): read it with get_job_result

The read tool answers `returned`, `total`, `job_id`, `offset`, a blank line and the table. `merge` puts each result in place of
the note line of its table, in the order of the answer, so a `scope` all answer keeps its two tables.
"""

import re
from typing import Any, Dict, List

from infrastructure.outbound.mcp.job_protocol import JobProtocol, JobRef
from infrastructure.outbound.mcp.job_protocols.common import read_state

_NOTE_LINE = re.compile(r"^note: pending:[^\r\n]*", re.MULTILINE)
_JOB_ID = re.compile(r"\bas job ([A-Za-z0-9_-]+)")
_STEP_PENDING = re.compile(r"\(pending\)")


class DynamicsPending(JobProtocol):
    name = "dynamics_pending"

    def detect(self, answer: str) -> List[JobRef]:
        # a `pending` note whose id cannot be read is still a job: JobRef("") makes the follow-up fail, it is not "no job"
        return [JobRef(_id.group(1) if (_id := _JOB_ID.search(note.group(0))) else "") for note in _NOTE_LINE.finditer(answer)]

    def read_arguments(self, job: JobRef) -> Dict[str, Any]:
        return {"job_id": job.job_id}

    def state(self, answer: str) -> str:
        return read_state(answer)

    def merge(self, answer: str, results: List[str]) -> str:
        parts = iter(results)
        merged = _NOTE_LINE.sub(lambda _: next(parts).strip("\r\n"), answer)
        # the `coverage` line still lists the steps as pending: they are done now
        return "\n".join(_STEP_PENDING.sub("(done)", line) if line.startswith("coverage:") else line for line in merged.split("\n"))

    def cancel_arguments(self, job: JobRef) -> Dict[str, Any]:
        return {"job_id": job.job_id}
