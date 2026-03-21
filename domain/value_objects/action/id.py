
from dataclasses import dataclass
import json

ErrActionIdEmpty = ValueError("Action id cannot be empty")

schema_path = "schema/response/actions/actions.id.schema.json"

@dataclass(frozen=True)
class Id:
    value: str

    def validate(self):
        if not self.value or self.value == "":
            raise ErrActionIdEmpty

    def get_value(self):
        return self.value

def create_id(value: str):
    action_id = Id(value)
    action_id.validate()
    return action_id

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic