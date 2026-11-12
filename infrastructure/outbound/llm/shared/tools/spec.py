# ===============================================
#  TOOL SPEC
#  A tool as the model sees it, with no SDK type: a name, a description,
#  a JSON Schema of the arguments and the function that runs it.
# ===============================================

from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Any]
