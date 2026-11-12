from dataclasses import dataclass
from typing import Any, Dict


# -----------------------------------------------
#  WHICH TOOLS A STEP MAY USE (PR-005 section 5, T-05.13)
#  A level (profile, flow, step) names whole servers and/or single tools (`server.tool`, or a bare name when one server has it).
#  A level that names nothing sets no limit. The tools a step may use are those every level that is set allows.
# -----------------------------------------------


@dataclass(frozen=True)
class ToolLimit:
    """What ONE level allows: whole servers and single tools."""
    servers: frozenset = frozenset()
    tools: frozenset = frozenset()

    @staticmethod
    def of(definition: Dict[str, Any]) -> "ToolLimit":
        return ToolLimit(frozenset(definition.get("servers") or ()), frozenset(definition.get("tools") or ()))

    def allows(self, server: str, tool: str) -> bool:
        return server in self.servers or tool in self.tools or f"{server}.{tool}" in self.tools

    def may_use(self, server: str) -> bool:
        """Whether some tool of the server can be allowed (a bare tool name may belong to any server)."""
        return server in self.servers or any("." not in name or name.startswith(f"{server}.") for name in self.tools)
