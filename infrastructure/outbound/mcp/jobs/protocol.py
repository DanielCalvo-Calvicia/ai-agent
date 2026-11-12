"""How a server says that a tool answer is a job to read later (ADR-018, T-07.3).

A protocol is plain code on text: it never calls a server. `detect` finds the jobs in an answer, `state` says what an answer
read from a job is (done, running or not understood), the two `*_arguments` methods say what to send to the server's read tool
and cancel tool (their names are in the server file: `job_read_tool`, `job_cancel_tool`), and `merge` puts the results in
place of the jobs. The follow-up loop (follow_up.py, T-07.4) does the calls, the waits and the budget. Nothing here logs
or keeps an answer. The protocols that exist are in registry.py; the check of a server file's job settings is in settings.py.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

NO_JOBS = "none"   # the default: the server has no jobs, so nothing is followed

# What an answer read from a job says (JobProtocol.state)
DONE, RUNNING, UNKNOWN = "done", "running", "unknown"


@dataclass(frozen=True)
class JobRef:
    """One job found in an answer: its id and, when the server gave one, the offset to read from."""
    job_id: str
    offset: Optional[int] = None


class JobProtocol(ABC):
    name: str

    @abstractmethod
    def detect(self, answer: str) -> List[JobRef]:
        """The jobs an answer holds, one per table, in the order of the answer; empty when it holds none. Never raises."""

    @abstractmethod
    def read_arguments(self, job: JobRef) -> Dict[str, Any]:
        """The arguments of the server's read tool for this job."""

    @abstractmethod
    def state(self, answer: str) -> str:
        """What an answer read from a job says: DONE (the result), RUNNING (not finished, read it again) or UNKNOWN (a shape
        this protocol does not understand). Never raises."""

    @abstractmethod
    def merge(self, answer: str, results: List[str]) -> str:
        """The answer of the call with the result of each of its jobs (`results[i]` is the one of `detect(answer)[i]`) in place
        of the job. Called only when every job is DONE."""

    @abstractmethod
    def cancel_arguments(self, job: JobRef) -> Dict[str, Any]:
        """The arguments of the server's cancel tool for this job."""


class NoJobs(JobProtocol):
    """The server has no jobs: an answer is the result, whatever it says."""
    name = NO_JOBS

    def detect(self, answer: str) -> List[JobRef]:
        return []

    def read_arguments(self, job: JobRef) -> Dict[str, Any]:
        return {}

    def state(self, answer: str) -> str:
        return DONE

    def merge(self, answer: str, results: List[str]) -> str:
        return answer

    def cancel_arguments(self, job: JobRef) -> Dict[str, Any]:
        return {}
