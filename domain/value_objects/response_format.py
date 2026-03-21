from typing import Union, Dict, Any
from dataclasses import dataclass


@dataclass(frozen=True)
class ResponseFormat:
    name: str
    schema: Dict[str, Any]

    def __post_init__(self):
        if not self.name:
            raise ValueError("Schema name cannot be empty")
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": self.name,
                "schema": self.schema
            }
        }