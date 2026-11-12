from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from application.dtos.outbound.tools import ToolDefinition, ToolScope


class McpToolsPort(ABC):
    """What the agent needs to know about MCP servers: which tools each one offers."""

    @abstractmethod
    def list_tools(self, server_name: str) -> List[ToolDefinition]:
        raise NotImplementedError

    def call_tool(self, tool_name: str, arguments: Dict[str, Any], scope: Optional[ToolScope] = None) -> Dict[str, Any]:
        """Calls one tool and returns its answer as `{"result": text, "is_error": False}` or `{"error": text, "is_error": True}`. Not
        abstract: a port that cannot call a tool (a fake) raises NotImplementedError and the caller falls back to the LLM operator."""
        raise NotImplementedError
