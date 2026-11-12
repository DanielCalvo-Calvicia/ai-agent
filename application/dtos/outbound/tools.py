# The classes the outbound adapters exchange with the application. They are the domain's own classes, not copies:
# an adapter imports them from here and never from `domain/` (tests/test_clean_architecture.py).

from domain.value_objects.llm_request.tool import ToolDefinition
from domain.value_objects.tools.tool_call_record import ToolCallRecord
from domain.value_objects.tools.tool_scope import ToolScope

__all__ = ["ToolDefinition", "ToolCallRecord", "ToolScope"]
