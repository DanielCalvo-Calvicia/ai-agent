"""One configured MCP server, read from its entry in `MCPClientManager.configs` (`{"name", "type", "config": {...}}`, see config.py).

Everything that needs a field of a server file reads it here, so the shape of the entry is known in one place. The entry stays a
plain dict in the manager (the tests give it fakes); this is a frozen view of it. Nothing here opens a connection or logs.
"""

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

from infrastructure.outbound.mcp.jobs.protocol import NO_JOBS


@dataclass(frozen=True)
class McpServer:
    name: str
    type: str
    url: Optional[str]
    allowed_tools: Optional[Tuple[str, ...]]     # None: the server file does not limit its tools
    job_protocol: Any                            # the `job_protocol` of the file as written (config.py checked it); `none` without the field
    job_read_tool: Optional[str]
    job_cancel_tool: Optional[str]
    job_recall_tools: Tuple[str, ...]

    @classmethod
    def from_entry(cls, name: str, entry: Dict[str, Any]) -> "McpServer":
        config = entry.get("config") or {}
        allowed = config.get("allowed_tools")
        return cls(
            name=name,
            type=entry.get("type", "sse"),
            url=config.get("url"),
            allowed_tools=tuple(allowed) if isinstance(allowed, (list, tuple)) else None,
            job_protocol=config.get("job_protocol", NO_JOBS),
            job_read_tool=config.get("job_read_tool"),
            job_cancel_tool=config.get("job_cancel_tool"),
            job_recall_tools=tuple(config.get("job_recall_tools") or ()),
        )

    @classmethod
    def find(cls, configs: Optional[Mapping[str, Dict[str, Any]]], name: str) -> Optional["McpServer"]:
        """The server called `name` in a manager's `configs`, or None (also when there are no configs at all)."""
        entry = (configs or {}).get(name)
        return None if entry is None else cls.from_entry(name, entry)
