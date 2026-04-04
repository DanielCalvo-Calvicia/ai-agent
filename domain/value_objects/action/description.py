
from dataclasses import dataclass
import json

ErrActionDescriptionEmpty = ValueError("Action description cannot be empty")

schema_path = "schema/response/basic/actions/actions.description.schema.json"

@dataclass(frozen=True)
class Description:
    value: str

    def validate(self):
        if not self.value or self.value == "":
            raise ErrActionDescriptionEmpty

    def get_value(self):
        return self.value

def create_description(value: str):
    description = Description(value)
    description.validate()
    return description

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic