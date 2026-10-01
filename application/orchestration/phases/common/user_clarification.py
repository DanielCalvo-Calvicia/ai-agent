# Phase 99 - User Clarification
# When a flow must pause, turns the missing inputs into a short message for the user.
# It has no prompt file and no response schema: its prompt is the constant below and it answers with plain text.

from domain.value_objects.model import GithubModels

# --- What this phase uses ---------------------------------------------------
PHASE_ID = 99
STEP_NAME = "user_clarification"
MODEL_ENV_VAR = "AI_AGENT_MODEL_PHASE_99"
DEFAULT_MODEL = GithubModels.GPT_4_1
INTENT = ("clarification_request", (), 1.0)
TEMPERATURE = 0.7
MAX_TOKENS = 2000
DEFAULT_MESSAGE = "Additional information is required to proceed. Please provide more details."
SYSTEM_PROMPT = (
    "You are communicating directly with an end user. "
    "Write a clear, friendly message asking for the information listed below. "
    "Be concise. Do not expose internal system details."
)
# -----------------------------------------------------------------------------
