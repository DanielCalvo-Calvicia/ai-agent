
from dataclasses import dataclass
import json

ErrSummaryEmpty = ValueError("Summary cannot be empty")

schema_path = "schema/response/user_goal/user_goal.summary.schema.json"

@dataclass(frozen=True)
class Summary:
    value: str

    def validate(self):
        if not self.value or self.value == "":
            raise ErrSummaryEmpty

    def get_value(self):
        return self.value

def create_summary(value: str):
    summary = Summary(value)
    summary.validate()
    return summary

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic