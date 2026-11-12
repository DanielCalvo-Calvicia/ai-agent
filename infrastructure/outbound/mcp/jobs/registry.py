"""The job protocols that exist, by name (ADR-018). A server file names one in `job_protocol`; without the field it is `none`.

Dependencies go one way: protocol.py (the interface) <- protocols/ (the built-in ones) <- this file, so no import is lazy.
A new protocol is one file in protocols/ and one entry below.
"""

from typing import Any, Dict, List

from infrastructure.outbound.mcp.jobs.protocol import JobProtocol, NoJobs
from infrastructure.outbound.mcp.jobs.protocols.dynamics_pending import DynamicsPending
from infrastructure.outbound.mcp.jobs.protocols.dynamics_v1 import DynamicsV1

_PROTOCOLS: Dict[str, JobProtocol] = {protocol.name: protocol for protocol in (NoJobs(), DynamicsPending(), DynamicsV1())}


def known_protocols() -> List[str]:
    return sorted(_PROTOCOLS)


def get_protocol(name: Any) -> JobProtocol:
    """The protocol called `name`; an unknown name or one that is not text is a ValueError (the config loader checks first)."""
    if not isinstance(name, str) or name not in _PROTOCOLS:
        raise ValueError(f"unknown job protocol {name!r}; known: {', '.join(known_protocols())}")
    return _PROTOCOLS[name]
