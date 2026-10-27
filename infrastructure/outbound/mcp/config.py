import json
import os
import re
from typing import Any, Dict, List, Optional

from shared_logging import get_logger

logger = get_logger(__name__)

DEFAULT_MCPS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'mcps')


# Protocols the MCP client can talk to. Servers of other types are ignored.
SUPPORTED_TYPES = ("sse",)

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


def load_supported_mcp_configs(mcps_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """The configured MCP servers the agent can actually use (see SUPPORTED_TYPES)."""
    supported: List[Dict[str, Any]] = []

    for server in load_mcp_configs(mcps_dir):
        if server["type"] in SUPPORTED_TYPES:
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
