# Phase 20 - Motion Planner
# Works out which arm movements the user asked for, as an ordered list. When a detail is missing
# (which arm, how far) it says so in next_step and the flow asks the user. A message that asks for
# no movement at all gets an empty list: motion-flow sees every message, not only movement requests.

from domain.value_objects.model import GithubModels
from domain.value_objects.motion.movement import ARMS, DIRECTIONS, Movement

from application.orchestration.state.motion_state import MotionFlowState
from application.orchestration.phases.phase import PhaseSpec
from application.orchestration.support.schemas import SchemaRef, schema_properties

# --- What this phase uses ---------------------------------------------------
PHASE_ID = 20
STEP_NAME = "motion_planner"
MODEL_ENV_VAR = "AI_AGENT_MODEL_PHASE_20"
DEFAULT_MODEL = GithubModels.GPT_4_1
PROMPT_FILE = "prompts/20_motion_planner.txt"
FORMAT_NAME = "motion_planner_phase20_response_format"
INTENT = ("decision_support", ("information_request",), 0.9)
REQUIRED = ("is_motion_request", "movements", "next_step")
SCHEMAS = {
    "next_step": SchemaRef("advanced/next_steps/next_step.schema.json", "next_step"),
}
SCHEMA = {
    "is_motion_request": {
        "type": "boolean",
        "description": "True when the user asked the robot to move an arm, even if a detail is still missing",
    },
    "movements": {
        "type": "array",
        "description": "The movements to run, in order. Empty when no movement was asked for or a detail is missing",
        "items": {
            "type": "object",
            "required": ["arm", "degrees", "direction"],
            "additionalProperties": False,
            "properties": {
                "arm": {"type": "string", "enum": list(ARMS), "description": "Which arm moves"},
                "degrees": {"type": "number", "description": "Degrees of rotation, signed: 90 then -90 returns the arm"},
                "direction": {"type": "string", "enum": list(DIRECTIONS), "description": "Direction of the rotation"},
            },
        },
    },
}
# -----------------------------------------------------------------------------


def _properties():
    return {**SCHEMA, **schema_properties(SCHEMAS)}


def movement_from(item: dict) -> Movement:
    """One movement as the planner wrote it. A degrees value that is not a number becomes NaN: the validator refuses it."""
    try:
        degrees = float(item.get("degrees"))
    except (TypeError, ValueError):
        degrees = float("nan")

    return Movement(arm=str(item.get("arm", "")), degrees=degrees, direction=str(item.get("direction", "")))


def _apply(state: MotionFlowState, response) -> None:
    raw = response.raw or {}
    state.motion_requested = bool(raw.get("is_motion_request", False))
    state.movements = [movement_from(item) for item in (raw.get("movements") or []) if isinstance(item, dict)]
    state.next_step = response.next_step


MOTION_PLANNER = PhaseSpec(
    id=PHASE_ID,
    step_name=STEP_NAME,
    prompt_file=PROMPT_FILE,
    model=DEFAULT_MODEL,
    intent=INTENT,
    format_name=FORMAT_NAME,
    required=REQUIRED,
    properties=_properties,
    build_input=lambda state: state.message_with_history(),
    apply=_apply,
)
