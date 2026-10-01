# ===============================================
#  ANSWER CHECK (phase 9)
#  The user replied to a question of the assistant. Was it the answer,
#  a yes or a no, a reply that does not answer, or a request to stop?
# ===============================================

from dataclasses import dataclass
from typing import Optional

from application.orchestration.state.paused_run import CONFIRMATION, PausedRun
from application.orchestration.engine.phase_runner import PhaseRunner
from application.orchestration.phases.common.answer_checker import (  # the verdicts belong to the phase
    ANSWERED,
    CONFIRMED,
    DECLINED,
    NOT_ANSWERED,
    STOP,
    make_answer_checker,
)

FALLBACK_MESSAGE = "I did not understand your reply. Could you answer my question, or tell me to stop?"


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
        response = self.runner.run_phase(make_answer_checker(paused, user_reply), paused.state)
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
