# ===============================================
#  ANSWER CHECK (phase 9)
#  The user replied to a question of the assistant. Was it the answer,
#  a yes or a no, a reply that does not answer, or a request to stop?
# ===============================================

from dataclasses import dataclass
from typing import Optional

from application.orchestration.flow_state import FlowState
from application.orchestration.paused_run import CONFIRMATION, PausedRun
from application.orchestration.phase import PhaseSpec
from application.orchestration.phase_runner import PhaseRunner
from domain.value_objects.model import GithubModels

ANSWERED = "answered"
CONFIRMED = "confirmed"
DECLINED = "declined"
NOT_ANSWERED = "not_answered"
STOP = "stop"

ANSWER_CHECK_PHASE_ID = 9

FALLBACK_MESSAGE = "I did not understand your reply. Could you answer my question, or tell me to stop?"

_SCHEMA = {
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


@dataclass
class Check:
    verdict: str
    answer: str = ""
    message: str = ""


class AnswerChecker:
    def __init__(self, runner: PhaseRunner) -> None:
        self.runner = runner

    def check(self, paused: PausedRun, user_reply: str) -> Check:
        """One LLM call. The verdict is always one that fits the kind of question that was asked."""
        spec = PhaseSpec(
            id=ANSWER_CHECK_PHASE_ID,
            model=GithubModels.GPT_4_1_MINI,
            intent=("clarification_request", (), 0.9),
            format_name="answer_checker_phase9_response_format",
            required=("verdict", "answer", "message_to_user"),
            properties=lambda: _SCHEMA,
            build_input=lambda state: {
                "kind": paused.kind,
                "question_asked": paused.question,
                "requested_items": paused.requested_items,
                "original_request": state.message,
                "user_reply": user_reply,
            },
            apply=lambda state, response: None,
        )

        response = self.runner.run_phase(spec, paused.state)
        raw = response.raw or {}

        return self._fit(paused.kind, Check(
            verdict=str(raw.get("verdict", "")),
            answer=str(raw.get("answer", "") or ""),
            message=str(raw.get("message_to_user", "") or ""),
        ))

    @staticmethod
    def _fit(kind: str, check: Check) -> Check:
        """Turns a verdict that does not fit the question into the closest one that does."""
        confirmation = kind == CONFIRMATION

        if check.verdict == STOP:
            return check
        if check.verdict in (ANSWERED, CONFIRMED) and confirmation:
            return Check(CONFIRMED)
        if check.verdict in (ANSWERED, CONFIRMED) and not confirmation:
            return Check(ANSWERED, answer=check.answer)
        if check.verdict == DECLINED and confirmation:
            return check

        return Check(NOT_ANSWERED, message=check.message or FALLBACK_MESSAGE)
