from dataclasses import dataclass, field
from typing import Any, Dict, List

ErrActionMcpContextServerIdEmpty = ValueError("Action mcp context server id cannot be empty")
ErrActionMcpContextToolNameEmpty = ValueError("Action mcp context tool name cannot be empty")
ErrActionMcpContextParametersEmpty = ValueError("Action mcp context parameters cannot be empty")


@dataclass(frozen=True)
class McpContext:
    server_id: str
    tool_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.validate()

        object.__setattr__(self, "server_id", self.server_id.strip())
        object.__setattr__(self, "tool_name", self.tool_name.strip())
        object.__setattr__(self, "parameters", self.parameters)

    def validate(self):
        self._validate_server_id()
        self._validate_tool_name()
        self._validate_parameters()

    def _validate_server_id(self):
        if not self.server_id or self.server_id == "":
            raise ErrActionMcpContextServerIdEmpty
        
    def _validate_tool_name(self):
        if not self.tool_name or self.tool_name == "":
            raise ErrActionMcpContextToolNameEmpty

    def _validate_parameters(self):
        if not self.parameters or self.parameters == {}:
            raise ErrActionMcpContextParametersEmpty

def create_mcp_context(server_id: str, tool_name: str, parameters: Dict[str, Any]):
    mcp_context = McpContext(server_id, tool_name, parameters)
    mcp_context.validate()
    return mcp_context
       
