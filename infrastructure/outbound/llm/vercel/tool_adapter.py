# ===============================================
#  VERCEL TOOL ADAPTER
#  Wraps the ToolSpec objects of shared/tools into ai_sdk Tools.
# ===============================================

from typing import Any, List, Optional

from ai_sdk.tool import Tool

from infrastructure.outbound.llm.shared.providers.config import LLMConfig
from infrastructure.outbound.llm.shared.tools.resolver import resolve_tool_specs
from infrastructure.outbound.llm.shared.tools.spec import ToolSpec


def resolve_tools(config: LLMConfig, tools: Optional[list]) -> List[Any]:
    """The tools of a payload as ai_sdk Tools (an entry that already is one is kept as is)."""
    return [_to_sdk_tool(spec) if isinstance(spec, ToolSpec) else spec
            for spec in resolve_tool_specs(config, tools)]


def _to_sdk_tool(spec: ToolSpec) -> Tool:
    return Tool(
        name=spec.name,
        description=spec.description,
        parameters=spec.parameters,
        handler=spec.handler,
    )
