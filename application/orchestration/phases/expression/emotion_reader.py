# Phase 30 - Emotion Reader
# Reads the feeling in an exchange (what the user said and what the robot answers) so the robot can move its arms
# while it speaks. It names an emotion, how strong it is and, optionally, a few movements of its own.

from domain.operations.gesture import DEFAULT_EMOTION, DEFAULT_INTENSITY, EMOTIONS, INTENSITIES
from domain.value_objects.llm_request.model import GithubModels
from domain.value_objects.movement.movement import Movement

from application.orchestration.phases.movement.motion_planner import movement_from
from application.orchestration.phases.phase import PhaseSpec
from application.orchestration.state.expression_state import as_expression
from application.orchestration.state.flow_state import FlowState
from application.orchestration.support.schemas import SchemaRef, schema_properties

# --- What this phase uses ---------------------------------------------------
PHASE_ID = 30
STEP_NAME = "emotion_reader"
MODEL_ENV_VAR = "AI_AGENT_MODEL_PHASE_30"
DEFAULT_MODEL = GithubModels.GPT_4_1
PROMPT_FILE = "prompts/30_emotion_reader.txt"
FORMAT_NAME = "emotion_reader_phase30_response_format"
INTENT = ("decision_support", ("information_request",), 0.9)
REQUIRED = ("emotion", "intensity", "improvised")
SCHEMAS = {
    "emotion": SchemaRef("expression/emotion.schema.json", "emotion"),
    "intensity": SchemaRef("expression/intensity.schema.json", "intensity"),
    "improvised": SchemaRef("expression/improvised/improvised.schema.json", "improvised"),
}
MAX_IMPROVISED = 3
# -----------------------------------------------------------------------------


def _properties():
    return schema_properties(SCHEMAS)


def _build_input(state: FlowState) -> str:
    state = as_expression(state)
    return f"What the user said:\n{state.message}\n\nWhat the robot answers:\n{state.reply}"


def _apply(state: FlowState, response) -> None:
    state = as_expression(state)
    raw = response.raw or {}

    emotion = str(raw.get("emotion") or "").strip().lower()
    state.emotion = emotion if emotion in EMOTIONS else DEFAULT_EMOTION

    try:
        intensity = int(raw.get("intensity"))
    except (TypeError, ValueError):
        intensity = DEFAULT_INTENSITY
    state.intensity = intensity if intensity in INTENSITIES else DEFAULT_INTENSITY

    items = [item for item in (raw.get("improvised") or []) if isinstance(item, dict)]
    state.improvised = [movement_from(item) for item in items[:MAX_IMPROVISED]]


EMOTION_READER = PhaseSpec(
    id=PHASE_ID,
    step_name=STEP_NAME,
    prompt_file=PROMPT_FILE,
    model=DEFAULT_MODEL,
    intent=INTENT,
    format_name=FORMAT_NAME,
    required=REQUIRED,
    properties=_properties,
    build_input=_build_input,
    apply=_apply,
)
