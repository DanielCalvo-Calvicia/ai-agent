# Phase 6 - Data Engineer
# Cleans the raw result of an MCP tool call before other actions use it. One LLM call per MCP action.

from domain.value_objects.model import GithubModels

from application.orchestration.phases.phase import ActionPhaseSpec
from application.orchestration.support.schemas import ACTIONS_SCHEMA_FILE

# --- What this phase uses ---------------------------------------------------
PHASE_ID = 6
STEP_NAME = "data_engineer"
MODEL_ENV_VAR = "AI_AGENT_MODEL_PHASE_6"
DEFAULT_MODEL = GithubModels.GPT_4_1
PROMPT_FILE = "prompts/6_data_engineer.txt"
FORMAT_NAME = "phase6_single_action_response_format"
INTENT = ("decision_support", (), 0.9)
ACTIONS_SCHEMA = ACTIONS_SCHEMA_FILE
# -----------------------------------------------------------------------------

DATA_ENGINEER = ActionPhaseSpec(
    id=PHASE_ID,
    step_name=STEP_NAME,
    prompt_file=PROMPT_FILE,
    model=DEFAULT_MODEL,
    intent=INTENT,
    format_name=FORMAT_NAME,
    schema_file=ACTIONS_SCHEMA,
)
