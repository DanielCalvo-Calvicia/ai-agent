# ===============================================
#  RESPONSE AS JSON
#  The structured Response of a run as plain data, in the shape the LLM answers (the sections of schema/response), so a client can
#  read it (`output` of /session/message) and send it back (`inputs` of the next request). The token usage and the raw answer of
#  the model are not part of it: they describe the cost of one internal call and `raw` may hold the model's unfiltered text.
# ===============================================

from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Dict

from domain.entities.llm_response.response import Response

# The parts of a Response that stay inside the service.
INTERNAL = ("tokens_usage", "raw", "text")


def to_plain(value: Any) -> Any:
    """Any domain object as plain data. A value object that only wraps a `value` becomes that value; subactions are a list."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_plain(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        names = [f.name for f in fields(value)]
        if names == ["value"]:
            return to_plain(getattr(value, "value"))
        plain: Dict[str, Any] = {}
        for name in names:
            item = getattr(value, name)
            if name == "subactions" and isinstance(item, dict):
                item = list(item.values())              # the schema asks for a list; the domain keeps them by id
            plain[name] = to_plain(item)
        return plain
    return str(value)


def response_to_json(response: Response) -> Dict[str, Any]:
    """The sections the Response has (a section it does not have is left out), without the internal parts."""
    plain = to_plain(response)
    return {name: section for name, section in plain.items() if name not in INTERNAL and section is not None}
