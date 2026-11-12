# ===============================================
#  TOOL HANDLERS
#  The function that runs a tool: through the MCP tool executor, or a mock answer without one.
# ===============================================

from infrastructure.outbound.llm.shared.providers.config import LLMConfig


def handler_for(config: LLMConfig, name: str, scope=None):
    executor = config.tool_executor
    if executor:
        if scope is not None:
            return lambda **kwargs: executor.execute(name, kwargs, scope=scope)
        return lambda **kwargs: executor.execute(name, kwargs)
    return lambda **kwargs: {"status": "success", "tool": name, "args": kwargs}
