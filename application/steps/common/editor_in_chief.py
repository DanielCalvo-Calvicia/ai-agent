# Phase 8 - Editor in Chief
# Polishes the draft and produces the final response for the user.

from domain.value_objects.llm_request.model import GoogleModels

from application.steps.phase import PhaseSpec
from application.engine.support.schemas import SchemaRef, schema_properties
from application.steps.registry import register_step

# --- What this phase uses ---------------------------------------------------
PHASE_ID = 8
STEP_NAME = "editor_in_chief"
DEFAULT_MODEL = GoogleModels.GEMINI_3_6_FLASH
PROMPT_FILE = "prompts/8_editor_in_chief.txt"
FORMAT_NAME = "editor_in_chief_phase8_response_format"
INTENT = ("decision_support", ("information_request",), 0.9)
REQUIRED = ("user_goal", "next_step")
SCHEMAS = {
    "user_goal": SchemaRef("general/user_goal/user_goal.schema.json", "user_goal"),
    "next_step": SchemaRef("general/next_steps/next_step.schema.json", "next_step"),
}
# -----------------------------------------------------------------------------
register_step(__name__, "llm")


def _apply(state, response):
    if response.user_goal:
        state.user_goal = response.user_goal
    if response.next_step:
        state.next_step = response.next_step


EDITOR_IN_CHIEF = PhaseSpec(
    id=PHASE_ID,
    step_name=STEP_NAME,
    prompt_file=PROMPT_FILE,
    model=DEFAULT_MODEL,
    intent=INTENT,
    format_name=FORMAT_NAME,
    required=REQUIRED,
    properties=lambda: schema_properties(SCHEMAS),
    build_input=lambda state: {
        "user_goal": state.user_goal,
        "constraints": state.constraints,
        "next_step": state.next_step,
    },
    apply=_apply,
)
