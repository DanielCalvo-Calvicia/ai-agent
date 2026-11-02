# Phase 7 - Draft Writer
# Synthesizes all action outputs into a first draft of the user response. The conversation flow runs it straight
# after identification (nothing was planned); the special flow runs it after the actions.

from domain.value_objects.llm_request.model import GoogleModels

from application.steps.phase import PhaseSpec
from application.engine.support.schemas import SchemaRef, schema_properties
from application.steps.registry import register_step

# --- What this phase uses ---------------------------------------------------
PHASE_ID = 7
STEP_NAME = "draft_writer"
DEFAULT_MODEL = GoogleModels.GEMINI_3_6_FLASH
PROMPT_FILE = "prompts/7_drawf_writter.txt"
FORMAT_NAME = "draft_writer_phase7_response_format"
INTENT = ("decision_support", ("information_request",), 0.9)
REQUIRED = ("user_goal",)
SCHEMAS = {
    "user_goal": SchemaRef("general/user_goal/user_goal.schema.json", "user_goal"),
}
# -----------------------------------------------------------------------------
register_step(__name__, "llm")


def _apply(state, response):
    if response.user_goal:
        state.user_goal = response.user_goal


def _build_input(state) -> dict:
    # user_message is the user's own words: the only sure sign of the language to answer in (the data may be in another one)
    return {
        "user_message": state.message,
        "user_goal": state.user_goal,
        "task_category": state.task_category,
        "actions": state.actions,
        "constraints": state.constraints,
    }


DRAFT_WRITER = PhaseSpec(
    id=PHASE_ID,
    step_name=STEP_NAME,
    prompt_file=PROMPT_FILE,
    model=DEFAULT_MODEL,
    intent=INTENT,
    format_name=FORMAT_NAME,
    required=REQUIRED,
    properties=lambda: schema_properties(SCHEMAS),
    build_input=_build_input,
    apply=_apply,
)
