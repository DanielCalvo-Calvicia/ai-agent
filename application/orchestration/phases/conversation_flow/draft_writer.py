# Phase 7 - Draft Writer
# Synthesizes all action outputs into a first draft of the user response.

from domain.value_objects.model import GithubModels

from application.orchestration.phases.phase import PhaseSpec
from application.orchestration.support.schemas import SchemaRef, schema_properties

# --- What this phase uses ---------------------------------------------------
PHASE_ID = 7
STEP_NAME = "draft_writer"
MODEL_ENV_VAR = "AI_AGENT_MODEL_PHASE_7"
DEFAULT_MODEL = GithubModels.GPT_4_1
PROMPT_FILE = "prompts/7_drawf_writter.txt"
FORMAT_NAME = "draft_writer_phase7_response_format"
INTENT = ("decision_support", ("information_request",), 0.9)
REQUIRED = ("user_goal",)
SCHEMAS = {
    "user_goal": SchemaRef("advanced/user_goal/user_goal.schema.json", "user_goal"),
}
# -----------------------------------------------------------------------------


def _apply(state, response):
    if response.user_goal:
        state.user_goal = response.user_goal


def _build_input(state) -> dict:
    user_message = {
        "user_goal": state.user_goal,
        "task_category": state.task_category,
        "actions": state.actions,
        "constraints": state.constraints,
    }
    if state.robot_context:
        user_message["robot_context"] = state.robot_context.as_dict()
    return user_message


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
