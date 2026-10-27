from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class MCPRouting:
    required_servers: List[str] = field(default_factory=list)

    def __post_init__(self):
        object.__setattr__(self, "required_servers", tuple(self.required_servers))

    def requires_routing(self) -> bool:
        return len(self.required_servers) > 0

def create_mcp_routing(required_servers: List[str] | str):
    if isinstance(required_servers, str):
        required_servers = [required_servers]
    mcp_routing = MCPRouting(required_servers=required_servers)
    return mcp_routing
