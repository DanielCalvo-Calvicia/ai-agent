from typing import Dict, Any
from dataclasses import dataclass

@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    read_only: bool = False     # the server says the tool changes nothing (MCP `readOnlyHint`); a tool that says nothing is not read-only (T-08.4)

    def to_openai_dict(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
