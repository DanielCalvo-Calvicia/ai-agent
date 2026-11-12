# ===============================================
#  MCP SERVERS
#  How the MCP servers are shown to the phases.
# ===============================================

from typing import Any, Dict, List, Optional

from application.ports.outbound.mcp_ports import McpToolsPort


def _offered(mcp_tools: McpToolsPort, server_name: str, read_only_only: bool) -> list:
    tools = mcp_tools.list_tools(server_name)
    return [t for t in tools if t.read_only] if read_only_only else tools


def server_names(mcp_list: list, mcp_tools: Optional[McpToolsPort] = None, read_only_only: bool = False) -> List[str]:
    """
    Names of the MCP servers the planner may choose. With a tools port, a server that offers no tools (it is down, or
    none of its tools is allowed) is left out for this message. Without a port every configured server is named.
    `read_only_only`: only a server that offers a read-only tool counts (the fast path, T-08.4).
    """
    return [server["name"] for server in mcp_list if not mcp_tools or _offered(mcp_tools, server["name"], read_only_only)]


def describe_servers(mcp_list: list, mcp_tools: Optional[McpToolsPort], read_only_only: bool = False) -> List[Dict[str, Any]]:
    """
    Each server as {"name", "tools": [{"name", "description", "parameters"}]}.
    The connection settings of the server are not shown to the LLM.
    Without a tools port every server is shown with empty `tools`. With one, a server that offers no tools (it is
    down, or none of its tools is allowed) is left out for this message. With `read_only_only` only the tools the server marks as
    read-only are shown, and a server with none is left out (the fast path has no safety gate, T-08.4).
    """
    servers: List[Dict[str, Any]] = []

    for server in mcp_list:
        tools = _offered(mcp_tools, server["name"], read_only_only) if mcp_tools else []
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
