# Phase 3 - Safety & Quality Gatekeeper
# Validates actions for safety and decides if user confirmation is needed.

from domain.value_objects.llm_request.model import GithubModels

from application.orchestration.phases.phase import PhaseSpec
from application.orchestration.support.schemas import SchemaRef, schema_properties

# --- What this phase uses ---------------------------------------------------
PHASE_ID = 3
STEP_NAME = "safety_quality_gatekeeper"
MODEL_ENV_VAR = "AI_AGENT_MODEL_PHASE_3"
DEFAULT_MODEL = GithubModels.GPT_4_1
PROMPT_FILE = "prompts/3_safety_quality_gatekeeper.txt"
FORMAT_NAME = "safety_quality_gatekeeper_phase3_response_format"
INTENT = ("decision_support", ("information_request",), 0.9)
REQUIRED = ("safety_and_validation", "next_step")
SCHEMAS = {
    "safety_and_validation": SchemaRef(
        "general/safety_and_validation/safety_and_validation.schema.json", "safety_and_validation"),
    "next_step": SchemaRef("general/next_steps/next_step.schema.json", "next_step"),
}
# -----------------------------------------------------------------------------


def _apply(state, response):
    state.safety_and_validation = response.safety_and_validation
    state.next_step = response.next_step


def _build_input(state) -> dict:
    user_message = {
        "actions": state.actions,
        "next_step": state.next_step,
    }
    if state.answers:
        user_message["user_answers"] = state.answers_as_dicts()
    return user_message


SAFETY_GATE = PhaseSpec(
    id=PHASE_ID,
    step_name=STEP_NAME,
    prompt_file=PROMPT_FILE,
    model=DEFAULT_MODEL,
    intent=INTENT,
    format_name=FORMAT_NAME,
    required=REQUIRED,
    properties=lambda: schema_properties(SCHEMAS),
    build_input=lambda state: _build_input(state),
    apply=_apply,
)
