# ===============================================
#  MCP AVAILABILITY CHECK (optional)
#  AI_AGENT_CHECK_MCP_<NAME>=1 asks for a reachability check of the MCP server <NAME> (its name in upper case, anything
#  that is not a letter or a digit as `_`): it lists the tools of the server, over the network, at start-up and each time
#  /available is called, and only LOGS the result. Unset or 0: nothing is checked. It never changes an answer.
# ===============================================

import os
import re
from typing import Iterable, List

from infrastructure.outbound.mcp.tool_catalog import MCPToolCatalog
from shared_logging import get_logger

logger = get_logger(__name__)

CHECK_VARIABLE_PREFIX = "AI_AGENT_CHECK_MCP_"


def check_variable(server_name: str) -> str:
    """AI_AGENT_CHECK_MCP_DYNAMICS_MICROSERVICE for the server `dynamics_microservice`."""
    return CHECK_VARIABLE_PREFIX + re.sub(r"[^A-Za-z0-9]", "_", server_name).upper()


class McpAvailabilityCheck:
    def __init__(self, catalog: MCPToolCatalog, server_names: Iterable[str]):
        self.catalog = catalog
        self.server_names = list(server_names)

    def run(self) -> List[str]:
        """Checks the servers that asked for it. Logs a warning naming each one that is not reachable (or offers no
        tools; never a URL, an argument or an answer). Returns the names of those servers. Blocking: one listing of up
        to 10 s per checked server."""
        unreachable: List[str] = []
        for name in self.server_names:
            if os.environ.get(check_variable(name), "").strip() != "1":
                continue
            tools = self.catalog.refresh_tools(name)
            if tools:
                logger.info("MCP server checked, it is reachable", server_name=name, tools=len(tools))
            else:
                logger.warning("MCP server is not reachable or offers no tools", server_name=name)
                unreachable.append(name)
        return unreachable
