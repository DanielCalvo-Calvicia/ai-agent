from dataclasses import dataclass
from typing import Any, Dict, Optional

from domain.value_objects.tools.tool_limit import ToolLimit


@dataclass(frozen=True)
class ToolScope:
    """The limits that apply to a step, one per level that is set. No limit at all: every tool."""
    limits: tuple = ()

    @staticmethod
    def of(*definitions: Optional[Dict[str, Any]]) -> "ToolScope":
        """`definitions`: the `tools` object of each level, None where a level sets nothing."""
        return ToolScope(tuple(ToolLimit.of(d) for d in definitions if isinstance(d, dict)))

    @property
    def unlimited(self) -> bool:
        return not self.limits

    def allows(self, server: str, tool: str) -> bool:
        return all(limit.allows(server, tool) for limit in self.limits)

    def may_use(self, server: str) -> bool:
        return all(limit.may_use(server) for limit in self.limits)
