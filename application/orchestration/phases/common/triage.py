# Phase 1 - Triage Specialist
# Classifies intent, extracts user goal and task category. Every flow starts with it.

from domain.value_objects.model import GithubModels

from application.orchestration.phases.phase import PhaseSpec
from application.orchestration.support.schemas import SchemaRef, schema_properties

# --- What this phase uses ---------------------------------------------------
PHASE_ID = 1
STEP_NAME = "triage_specialist"
MODEL_ENV_VAR = "AI_AGENT_MODEL_PHASE_1"
DEFAULT_MODEL = GithubModels.GPT_4_1_MINI
PROMPT_FILE = "prompts/1_triage_specialist.txt"
FORMAT_NAME = "triage_specialist_phase1_response_format"
INTENT = ("clarification_request", ("information_request",), 1.0)
REQUIRED = ("intent", "user_goal", "task_category", "next_step")
SCHEMAS = {
    "intent": SchemaRef("advanced/intent/intent.schema.json", "intent"),
    "user_goal": SchemaRef("advanced/user_goal/user_goal.schema.json", "user_goal"),
    "task_category": SchemaRef("advanced/task_category/task_category.schema.json", "task_category"),
    "next_step": SchemaRef("advanced/next_steps/next_step.schema.json", "next_step"),
}
# -----------------------------------------------------------------------------


TRIAGE = PhaseSpec(
    id=PHASE_ID,
    step_name=STEP_NAME,
    prompt_file=PROMPT_FILE,
    model=DEFAULT_MODEL,
    intent=INTENT,
    format_name=FORMAT_NAME,
    required=REQUIRED,
    properties=lambda: schema_properties(SCHEMAS),
    build_input=lambda state: state.message_with_history(),
    # The triage answer starts the state: every field it carries is taken.
    apply=lambda state, response: state.load_from(response),
)
