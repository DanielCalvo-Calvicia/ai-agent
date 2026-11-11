"""`dynamics_v1`: the shape of the documents of `dynamics_microservice` (T-01 fact F4, T-07.5, ADR-018).

A call that is not done answers `status: running` with a `job_id` and a `next_offset`; the whole answer is the job, and it is read
with the read tool giving `job_id` and, as `offset_rows`, the `next_offset`. `merge` gives the result of that one job.
"""

from typing import Any, Dict, List

from infrastructure.outbound.mcp.job_protocol import JobProtocol, JobRef
from infrastructure.outbound.mcp.job_protocols.common import head_lines, optional_int, read_state


class DynamicsV1(JobProtocol):
    name = "dynamics_v1"

    def detect(self, answer: str) -> List[JobRef]:
        head = head_lines(answer)
        if head.get("status", "").lower() != "running":
            return []
        return [JobRef(head.get("job_id", ""), optional_int(head.get("next_offset")))]    # no id: JobRef("") makes the follow-up fail

    def read_arguments(self, job: JobRef) -> Dict[str, Any]:
        arguments: Dict[str, Any] = {"job_id": job.job_id}
        if job.offset is not None:
            arguments["offset_rows"] = job.offset
        return arguments

    def state(self, answer: str) -> str:
        return read_state(answer)

    def merge(self, answer: str, results: List[str]) -> str:
        return results[0] if results else answer

    def cancel_arguments(self, job: JobRef) -> Dict[str, Any]:
        return {"job_id": job.job_id}
