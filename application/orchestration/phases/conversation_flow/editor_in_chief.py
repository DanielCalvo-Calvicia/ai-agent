# Phase 8 - Editor in Chief
# Polishes the draft and produces the final response for the user.

from domain.value_objects.model import GithubModels

from application.orchestration.phases.phase import PhaseSpec
from application.orchestration.support.schemas import SchemaRef, schema_properties

# --- What this phase uses ---------------------------------------------------
PHASE_ID = 8
STEP_NAME = "editor_in_chief"
MODEL_ENV_VAR = "AI_AGENT_MODEL_PHASE_8"
DEFAULT_MODEL = GithubModels.GPT_4_1
PROMPT_FILE = "prompts/8_editor_in_chief.txt"
FORMAT_NAME = "editor_in_chief_phase8_response_format"
INTENT = ("decision_support", ("information_request",), 0.9)
REQUIRED = ("user_goal", "next_step")
SCHEMAS = {
    "user_goal": SchemaRef("advanced/user_goal/user_goal.schema.json", "user_goal"),
    "next_step": SchemaRef("advanced/next_steps/next_step.schema.json", "next_step"),
}
# -----------------------------------------------------------------------------


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
