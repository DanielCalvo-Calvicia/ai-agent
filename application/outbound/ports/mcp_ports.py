from abc import ABC, abstractmethod
from typing import List

from domain.value_objects.llm_request.tool import ToolDefinition


class McpToolsPort(ABC):
    """What the agent needs to know about MCP servers: which tools each one offers."""

    @abstractmethod
    def list_tools(self, server_name: str) -> List[ToolDefinition]:
        raise NotImplementedError
