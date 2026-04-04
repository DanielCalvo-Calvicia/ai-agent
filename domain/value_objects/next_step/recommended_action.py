
from dataclasses import dataclass
import json

ErrRecommendedActionEmpty = ValueError("Recommended action cannot be empty")

schema_path = "schema/response/basic/next_step.recommended_action.schema.json"

@dataclass(frozen=True)
class RecommendedAction:
    value: str

    def validate(self):
        if not self.value or self.value == "":
            raise ErrRecommendedActionEmpty

    def get_value(self):
        return self.value

def create_recommended_action(value: str):
    action = RecommendedAction(value)
    action.validate()
    return action

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic