from dataclasses import dataclass, field
from typing import Any, Dict, List

from .expected_outcome import ExpectedOutcome, create_expected_outcome
from .summary import Summary, create_summary


@dataclass(frozen=True)
class UserGoal:
    summary: Summary
    expected_outcome: ExpectedOutcome

def create_user_goal(summary_value: str, expected_outcome_value: str):
    summary = create_summary(summary_value)
    expected_outcome = create_expected_outcome(expected_outcome_value)
    user_goal = UserGoal(summary, expected_outcome)
    return user_goal
