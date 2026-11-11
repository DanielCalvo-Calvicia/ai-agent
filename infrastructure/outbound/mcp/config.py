import json
import os
import re
from typing import Any, Dict, List, Optional

from infrastructure.outbound.mcp.job_protocol import job_protocol_problem
from shared_logging import get_logger

logger = get_logger(__name__)

DEFAULT_MCPS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'mcps')


# Protocols the MCP client can talk to. Servers of other types are ignored.
SUPPORTED_TYPES = ("sse", "streamable_http")

_ENV_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def expand_env(value: Any) -> Any:
    """``${NAME}`` in every string of a config becomes that environment variable (one that is not set stays as written).

    Lets a config file name a machine-specific path or URL without hardcoding it (``source=${MCP_FILESYSTEM_DIR}``).
    """
    if isinstance(value, str):
        return _ENV_REFERENCE.sub(lambda match: os.environ.get(match.group(1), match.group(0)), value)
    if isinstance(value, list):
        return [expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: expand_env(item) for key, item in value.items()}
    return value


def _unset_variables(value: Any) -> List[str]:
    """Names of the ``${NAME}`` references still in a value after expand_env (their variable is not set)."""
    return _ENV_REFERENCE.findall(value) if isinstance(value, str) else []


def load_supported_mcp_configs(mcps_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """The configured MCP servers the agent can actually use (see SUPPORTED_TYPES)."""
    supported: List[Dict[str, Any]] = []

    for server in load_mcp_configs(mcps_dir):
        if server["type"] in SUPPORTED_TYPES:
            unset = _unset_variables(server["config"].get("url"))
            if unset:
                logger.warning("MCP server url is not set, ignoring the server", server_name=server["name"], variables=unset)
                continue
            problem = job_protocol_problem(server["config"])
            if problem:
                logger.warning("MCP server job settings are not valid, ignoring the server", server_name=server["name"], problem=problem)
                continue
            supported.append(server)
        else:
            logger.warning("MCP server type is not supported, ignoring it", server_name=server["name"], server_type=server["type"])

    return supported


def load_mcp_configs(mcps_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Reads every .json file of the mcps folder (default: <project root>/mcps).
    Each file is { "server_name": { ...config } } and becomes
    {"name": server_name, "type": config.type (default "stdio"), "config": config}.
    """
    mcps_dir = os.path.abspath(mcps_dir or DEFAULT_MCPS_DIR)

    if not os.path.isdir(mcps_dir):
        logger.warning("MCP directory not found", path=mcps_dir)
        return []

    mcp_configs: List[Dict[str, Any]] = []
    for filename in sorted(os.listdir(mcps_dir)):
        if not filename.endswith('.json'):
            continue
        try:
            with open(os.path.join(mcps_dir, filename), 'r', encoding='utf-8') as f:
                data = expand_env(json.load(f))
            for server_name, config in data.items():
                mcp_configs.append({
                    "name": server_name,
                    "type": config.get("type", "stdio"),
                    "config": config,
                })
        except Exception:
            logger.exception("Error loading MCP config", filename=filename)

    return mcp_configs


def load_tool_snapshot(mcps_dir: Optional[str] = None) -> Dict[str, Optional[List[str]]]:
    """
    The MCP servers of mcps/*.json, whatever their type or url, and for each the tools its `allowed_tools` lists (None when it
    lists none). A profile may name only these (PR-005 section 9); the live list of a server is not asked.
    """
    return {server["name"]: (list(server["config"]["allowed_tools"]) if server["config"].get("allowed_tools") else None)
            for server in load_mcp_configs(mcps_dir)}
