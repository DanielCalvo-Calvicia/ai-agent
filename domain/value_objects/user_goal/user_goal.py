from dataclasses import dataclass, field
import json
from typing import Any, Dict, List

from .expected_outcome import ExpectedOutcome, create_expected_outcome
from .summary import Summary, create_summary

schema_path = "schema/response/user_goal/user_goal.schema.json"
schema_base_path = "schema/response/user_goal/user_goal.base.schema.json"

@dataclass(frozen=True)
class UserGoal:
    summary: Summary
    expected_outcome: ExpectedOutcome

def create_user_goal(summary_value: str, expected_outcome_value: str):
    summary = create_summary(summary_value)
    expected_outcome = create_expected_outcome(expected_outcome_value)
    user_goal = UserGoal(summary, expected_outcome)
    return user_goal

def get_schema() -> Dict[str, Any]:
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic

def get_base_schema():  
    # Load the base schema from your local file
    with open(schema_base_path + "user_goal.base.schema.json", 'r') as f:
        base_schema_dic = json.load(f)
    return base_schema_dic