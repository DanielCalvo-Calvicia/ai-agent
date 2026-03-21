
from dataclasses import dataclass
import json

ErrExpectedOutcomeEmpty = ValueError("Expected outcome cannot be empty")

schema_path = "schema/response/user_goal/user_goal.expected_outcome.schema.json"

@dataclass(frozen=True)
class ExpectedOutcome:
    value: str

    def validate(self):
        if not self.value or self.value == "":
            raise ErrExpectedOutcomeEmpty

    def get_value(self):
        return self.value

def create_expected_outcome(value: str):
    expected_outcome = ExpectedOutcome(value)
    expected_outcome.validate()
    return expected_outcome

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic