
from dataclasses import dataclass
import json

ErrActionTypeEmpty = ValueError("Action type cannot be empty")

schema_path = "schema/response/actions/actions.action_type.schema.json"

@dataclass(frozen=True)
class ActionType:
    value: str

    def validate(self):
        if not self.value or self.value == "":
            raise ErrActionTypeEmpty

    def get_value(self):
        return self.value

def create_action_type(value: str):
    action_type = ActionType(value)
    action_type.validate()
    return action_type

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic