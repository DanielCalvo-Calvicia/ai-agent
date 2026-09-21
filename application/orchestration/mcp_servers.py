# ===============================================
#  MCP SERVERS
#  How the MCP servers are shown to the phases.
# ===============================================

from typing import Any, Dict, List, Optional

from application.outbound.ports.mcp_ports import McpToolsPort


def server_names(mcp_list: list) -> List[str]:
    """Names of the configured MCP servers."""
    return [server["name"] for server in mcp_list]


def describe_servers(mcp_list: list, mcp_tools: Optional[McpToolsPort]) -> List[Dict[str, Any]]:
    """
    Each server as {"name", "tools": [{"name", "description", "parameters"}]}.
    The connection settings of the server are not shown to the LLM.
    Without a tools port, or when a server is unreachable, `tools` is empty.
    """
    servers: List[Dict[str, Any]] = []

    for server in mcp_list:
        tools = mcp_tools.list_tools(server["name"]) if mcp_tools else []
        servers.append({
            "name": server["name"],
            "tools": [
                {"name": t.name, "description": t.description, "parameters": t.parameters}
                for t in tools
            ],
        })

    return servers
