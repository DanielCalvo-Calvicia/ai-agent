"""The job settings of a server file (ADR-018): which protocol, and which tools read, cancel and call again. Checked when the
server files are loaded, so a server with settings that cannot work is ignored at start and never fails in the middle of a call."""

from typing import Any, Dict, Optional

from infrastructure.outbound.mcp.jobs.protocol import NO_JOBS
from infrastructure.outbound.mcp.jobs.registry import get_protocol


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
    recall = server_config.get("job_recall_tools")
    if recall is not None:
        if not isinstance(recall, list) or not all(isinstance(tool, str) and tool for tool in recall):
            return "job_recall_tools must be a list of tool names"
        outside = [tool for tool in recall if allowed and tool not in allowed]
        if outside:
            return f"job_recall_tools {outside[0]!r} is not in allowed_tools"
    for field, tool in (("job_read_tool", read_tool), ("job_cancel_tool", server_config.get("job_cancel_tool"))):
        if tool is None:
            continue
        if not isinstance(tool, str) or not tool:
            return f"{field} must be a tool name"
        if allowed and tool not in allowed:
            return f"{field} {tool!r} is not in allowed_tools"
    return None
