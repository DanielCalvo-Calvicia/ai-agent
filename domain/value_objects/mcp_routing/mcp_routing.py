from dataclasses import dataclass, field
from typing import Any, Dict, List

import json

schema_path = "schema/response/mcp_routing/mcp_routing.schema.json"
schema_base_path = "schema/response/mcp_routing/mcp_routing.base.schema.json" 
schema_required_servers_path = "schema/response/mcp_routing/mcp_routing.required_servers.schema.json"


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

def get_schema():
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic
def get_base_schema():
    with open(schema_base_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic
def get_required_servers_schema():
    with open(schema_required_servers_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic