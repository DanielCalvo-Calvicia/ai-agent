"""`dynamics_v1`: the jobs contract of `dynamics_microservice` since 2026-11-11 (T-07.5, ADR-018; its `docs/api/mcp.md`).

Every answer starts with `status: ok | running | error`. A call that is a job not finished answers `status: running` with a
`job_id` (and `retry_after_seconds`); a workflow of several tables repeats `status` (and, for a table that is a job, `job_id`)
in the block of each table under its `## title`, and the first line of the whole answer is `running` while any table is, so
each job is followed apart. The read tool answers `status: ok` with `returned`, `total`, `job_id`, `offset`, `complete` (and
`next_offset` when more rows exist) or, while the job works, `status: running` again.

`detect` gives one job per running table (or one for an answer that is a single job); `merge` puts the result of each job in
the block of its table and turns the first status line into `ok`. A result that is a first page (`complete: no`, with a
`next_offset`) is given as it is, with its hint: the other pages are not read (T-07.4).
"""

from typing import Any, Dict, List

from infrastructure.outbound.mcp.job_protocol import JobProtocol, JobRef
from infrastructure.outbound.mcp.job_protocols.common import head_lines, optional_int, read_state, split_sections


def _running_job(block: str) -> List[JobRef]:
    head = head_lines(block)
    if head.get("status", "").lower() != "running":
        return []
    return [JobRef(head.get("job_id", ""), optional_int(head.get("next_offset")))]    # no id: JobRef("") makes the follow-up fail


class DynamicsV1(JobProtocol):
    name = "dynamics_v1"

    def detect(self, answer: str) -> List[JobRef]:
        head, sections = split_sections(answer)
        if not sections:
            return _running_job(head)
        # the head of a several-table answer says `running` while any table does, but the ids are in the blocks of the tables
        return [job for section in sections for job in _running_job(section.split("\n", 1)[1] if "\n" in section else "")]

    def read_arguments(self, job: JobRef) -> Dict[str, Any]:
        arguments: Dict[str, Any] = {"job_id": job.job_id}
        if job.offset is not None:
            arguments["offset_rows"] = job.offset
        return arguments

    def state(self, answer: str) -> str:
        return read_state(answer)

    def merge(self, answer: str, results: List[str]) -> str:
        head, sections = split_sections(answer)
        if not sections:
            return results[0] if results else answer
        parts = iter(results)
        merged = []
        for section in sections:
            title, _, body = section.partition("\n")
            if _running_job(body):
                tail = section[len(section.rstrip("\n")):]                   # the blank lines that separate it from the next table
                merged.append(f"{title}\n{next(parts).strip(chr(10))}{tail}")
            else:
                merged.append(section)
        return _ready_head(head) + "".join(merged)

    def cancel_arguments(self, job: JobRef) -> Dict[str, Any]:
        return {"job_id": job.job_id}


def _ready_head(head: str) -> str:
    """The lines above the tables of a several-table answer, now that no table runs: the first `status` is `ok`, a summary value
    of `pending` is `done`, and the `steps` of the `coverage` line say `ran`."""
    lines, status_done = [], False
    for line in head.split("\n"):
        key, separator, value = line.partition(":")
        if separator and key.strip().lower() == "status" and not status_done:
            line, status_done = "status: ok", True
        elif separator and value.strip().lower() == "pending":
            line = f"{key}: done"
        elif line.startswith("coverage:"):
            line = line.replace("(pending)", "(ran)")
        lines.append(line)
    return "\n".join(lines)
