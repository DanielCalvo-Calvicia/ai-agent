# ===============================================
#  MCP SERVERS
#  How the MCP servers are shown to the phases.
# ===============================================

from typing import Any, Dict, List, Optional

from application.outbound.ports.mcp_ports import McpToolsPort


def server_names(mcp_list: list, mcp_tools: Optional[McpToolsPort] = None) -> List[str]:
    """
    Names of the MCP servers the planner may choose. With a tools port, a server that offers no tools (it is down, or
    none of its tools is allowed) is left out for this message. Without a port every configured server is named.
    """
    return [server["name"] for server in mcp_list if not mcp_tools or mcp_tools.list_tools(server["name"])]


def describe_servers(mcp_list: list, mcp_tools: Optional[McpToolsPort]) -> List[Dict[str, Any]]:
    """
    Each server as {"name", "tools": [{"name", "description", "parameters"}]}.
    The connection settings of the server are not shown to the LLM.
    Without a tools port every server is shown with empty `tools`. With one, a server that offers no tools (it is
    down, or none of its tools is allowed) is left out for this message.
    """
    servers: List[Dict[str, Any]] = []

    for server in mcp_list:
        tools = mcp_tools.list_tools(server["name"]) if mcp_tools else []
        if mcp_tools and not tools:
            continue
        servers.append({
            "name": server["name"],
            "tools": [
                {"name": t.name, "description": t.description, "parameters": t.parameters}
                for t in tools
            ],
        })

    return servers
