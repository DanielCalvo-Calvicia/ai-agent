# Phase 20 - Motion Planner
# Works out which arm movements the user asked for, as an ordered list. When a detail is missing
# (which arm, how far) it says so in next_step and the flow asks the user. A message that asks for
# no movement at all (triage can be wrong about the domain) gets an empty list and a spoken line.

from domain.value_objects.llm_request.model import GithubModels
from domain.value_objects.movement.movement import Movement

from application.orchestration.state.flow_state import FlowState
from application.orchestration.state.motion_state import as_motion
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
REQUIRED = ("is_motion_request", "movements", "spoken_reply", "next_step")
SCHEMAS = {
    "is_motion_request": SchemaRef("motion/is_motion_request.schema.json", "is_motion_request"),
    "movements": SchemaRef("motion/movements/movements.schema.json", "movements"),
    "spoken_reply": SchemaRef("motion/spoken_reply.schema.json", "spoken_reply"),
    "next_step": SchemaRef("general/next_steps/next_step.schema.json", "next_step"),
}
# -----------------------------------------------------------------------------


def _properties():
    return schema_properties(SCHEMAS)


def movement_from(item: dict) -> Movement:
    """One movement as the planner wrote it. A degrees value that is not a number becomes NaN: the validator refuses it."""
    raw_degrees = item.get("degrees")
    try:
        degrees = float(raw_degrees) if raw_degrees is not None else float("nan")
    except (TypeError, ValueError):
        degrees = float("nan")

    return Movement(arm=str(item.get("arm", "")), degrees=degrees, direction=str(item.get("direction", "")))


def _apply(state: FlowState, response) -> None:
    state = as_motion(state)
    raw = response.raw or {}
    state.motion_requested = bool(raw.get("is_motion_request", False))
    state.movements = [movement_from(item) for item in (raw.get("movements") or []) if isinstance(item, dict)]
    state.spoken_reply = str(raw.get("spoken_reply") or "")
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
