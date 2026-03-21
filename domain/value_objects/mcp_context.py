from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class McpContext:
    server_id: str
    tool_name: str
    parameters: Dict[str, Any]

    def __post_init__(self):
        object.__setattr__(self, "server_id", self.server_id.strip())
        object.__setattr__(self, "tool_name", self.tool_name.strip())
        object.__setattr__(self, "parameters", self.parameters) 