"""How a server says that a tool answer is a job to read later (ADR-018, T-07.3).

A protocol is plain code on text: it never calls a server. `detect` finds the jobs in an answer, `state` says what an answer
read from a job is (done, running or not understood), the two `*_arguments` methods say what to send to the server's read tool
and cancel tool (their names are in the server file: `job_read_tool`, `job_cancel_tool`), and `merge` puts the results in
place of the jobs. The follow-up loop (job_follow_up.py, T-07.4) does the calls, the waits and the budget. Nothing here logs
or keeps an answer.
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


_PROTOCOLS: Dict[str, JobProtocol] = {NO_JOBS: NoJobs()}


def register_protocol(protocol: JobProtocol) -> None:
    """Adds a protocol under its name (the built-in ones call this when job_protocols is imported)."""
    _PROTOCOLS[protocol.name] = protocol


def _load_built_in() -> None:
    """Imports the built-in protocols (which register themselves) the first time a name is asked; here and not at the top
    because they import this module."""
    import infrastructure.outbound.mcp.job_protocols  # noqa: F401


def known_protocols() -> List[str]:
    _load_built_in()
    return sorted(_PROTOCOLS)


def get_protocol(name: Any) -> JobProtocol:
    """The protocol called `name`; an unknown name or one that is not text is a ValueError (the config loader checks first)."""
    _load_built_in()
    if not isinstance(name, str) or name not in _PROTOCOLS:
        raise ValueError(f"unknown job protocol {name!r}; known: {', '.join(known_protocols())}")
    return _PROTOCOLS[name]


def protocol_name_of(server_config: Dict[str, Any]) -> Any:
    """The `job_protocol` of a server file's config; without the field, `none`."""
    return server_config.get("job_protocol", NO_JOBS)


def job_protocol_problem(server_config: Dict[str, Any]) -> Optional[str]:
    """Why the job settings of a server file cannot work, or None. A server with `none` needs nothing else."""
    name = protocol_name_of(server_config)
    try:
        get_protocol(name)
    except ValueError as error:
        return str(error)
    if name == NO_JOBS:
        return None
    read_tool = server_config.get("job_read_tool")
    if not isinstance(read_tool, str) or not read_tool:
        return f"job_protocol {name!r} needs a job_read_tool"
    allowed = server_config.get("allowed_tools")
    for field, tool in (("job_read_tool", read_tool), ("job_cancel_tool", server_config.get("job_cancel_tool"))):
        if tool is None:
            continue
        if not isinstance(tool, str) or not tool:
            return f"{field} must be a tool name"
        if allowed and tool not in allowed:
            return f"{field} {tool!r} is not in allowed_tools"
    return None
