# Phase 9 - Answer Checker
# The user replied to a question of the assistant. Was it the answer, a yes or a no,
# a reply that does not answer, or a request to stop? Any flow that pauses uses it.

from application.orchestration.state.flow_state import FlowState
from application.orchestration.state.paused_run import PausedRun
from application.orchestration.phases.phase import PhaseSpec
from domain.value_objects.model import GithubModels

# What the user's reply is.
ANSWERED = "answered"
CONFIRMED = "confirmed"
DECLINED = "declined"
NOT_ANSWERED = "not_answered"
STOP = "stop"

# --- What this phase uses ---------------------------------------------------
PHASE_ID = 9
STEP_NAME = "answer_checker"
MODEL_ENV_VAR = "AI_AGENT_MODEL_PHASE_9"
DEFAULT_MODEL = GithubModels.GPT_4_1_MINI
PROMPT_FILE = "prompts/9_answer_checker.txt"
FORMAT_NAME = "answer_checker_phase9_response_format"
INTENT = ("clarification_request", (), 0.9)
REQUIRED = ("verdict", "answer", "message_to_user")
SCHEMA = {
    "verdict": {
        "type": "string",
        "enum": [ANSWERED, CONFIRMED, DECLINED, NOT_ANSWERED, STOP],
        "description": "What the user's reply is",
    },
    "answer": {
        "type": "string",
        "description": "For 'answered': the information the user gave, restated clearly. Otherwise empty",
    },
    "message_to_user": {
        "type": "string",
        "description": "For 'not_answered': a short message saying what is still needed. Otherwise empty",
    },
}
# -----------------------------------------------------------------------------


def make_answer_checker(paused: PausedRun, user_reply: str) -> PhaseSpec:
    return PhaseSpec(
        id=PHASE_ID,
        step_name=STEP_NAME,
        prompt_file=PROMPT_FILE,
        model=DEFAULT_MODEL,
        intent=INTENT,
        format_name=FORMAT_NAME,
        required=REQUIRED,
        properties=lambda: SCHEMA,
        build_input=lambda state: _build_input(state, paused, user_reply),
        apply=lambda state, response: None,
    )


def _build_input(state: FlowState, paused: PausedRun, user_reply: str) -> dict:
    return {
        "kind": paused.kind,
        "question_asked": paused.question,
        "requested_items": paused.requested_items,
        "original_request": state.message,
        "user_reply": user_reply,
    }
