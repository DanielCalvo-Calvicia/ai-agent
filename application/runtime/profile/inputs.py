# ===============================================
#  PROFILE INPUTS
#  What a client sends in `inputs`: fields of the state (the `Response` of an earlier profile, or a field such as the `reply` a gesture
#  is made for). They are DATA, never instructions: only the fields the profile accepts, each read with the same code that reads an
#  LLM answer and the same domain checks. The token usage and the raw answer of a model are ignored. A required field that is missing
#  is refused before any model is called.
# ===============================================

from typing import Any, Callable, Dict, Optional

from application.engine.assemble import AssembledProfile
from application.engine.state.response_json import INTERNAL
from domain.entities.llm_response.response import Response

MISSING_INPUT = "MISSING_INPUT"
INVALID_INPUT = "INVALID_INPUT"

# The fields a Response carries; the others of the catalog (`reply`, `speech_seconds`, ...) are plain values.
RESPONSE_FIELDS = ("intent", "user_goal", "mcp_routing", "task_category", "actions", "missing_information", "constraints",
                   "safety_and_validation", "next_step")
SCALARS = {"reply": str, "speech_seconds": (int, float)}

ResponseReader = Callable[[dict], Response]


class InputsError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def read_inputs(profile: AssembledProfile, inputs: Optional[Dict[str, Any]], reader: Optional[ResponseReader]) -> Dict[str, Any]:
    """The inputs as the values of the state fields (domain objects and plain values). Raises InputsError."""
    inputs = {name: value for name, value in (inputs or {}).items() if name not in INTERNAL}
    allowed = set(profile.requires) | set(profile.accepts)

    missing = [name for name in profile.requires if name not in inputs]
    if missing:
        raise InputsError(MISSING_INPUT, f"The profile {profile.name!r} needs the input {', '.join(missing)}.")
    unknown = [name for name in inputs if name not in allowed]
    if unknown:
        raise InputsError(INVALID_INPUT, f"The profile {profile.name!r} does not take the input {', '.join(unknown)}.")

    values: Dict[str, Any] = {}
    sections = {name: inputs[name] for name in inputs if name in RESPONSE_FIELDS}
    if sections:
        if reader is None:
            raise InputsError(INVALID_INPUT, "The service cannot read structured inputs.")
        try:
            response = reader(sections)
        except Exception as error:                                   # a domain check or a missing key: the client sent it wrong
            raise InputsError(INVALID_INPUT, f"An input is not valid: {type(error).__name__}.") from None
        for name in sections:
            value = getattr(response, name, None)
            if value is None:
                raise InputsError(INVALID_INPUT, f"The input {name!r} is not valid.")
            values[name] = value

    for name, value in inputs.items():
        if name in RESPONSE_FIELDS:
            continue
        expected = SCALARS.get(name)
        if expected is None or isinstance(value, bool) or not isinstance(value, expected):
            raise InputsError(INVALID_INPUT, f"The input {name!r} is not valid.")
        values[name] = value
    return values
