
from dataclasses import dataclass
import json
from typing import List

ErrActionRequiredInputEmpty = ValueError("Required input name cannot be empty.")

schema_path = "schema/response/actions/actions.required_inputs.schema.json"

@dataclass(frozen=True)
class RequiredInputs:
    value: List[str]

    def validate(self):
        if not self.value or self.value == []:
            raise ErrActionRequiredInputEmpty

    def add_required_input(self, input_name: str):
        if not input_name.strip():
            raise ErrActionRequiredInputEmpty
        new_required_inputs = self.value + [input_name]
        object.__setattr__(self, "value", new_required_inputs)

    def get_value(self):
        return self.value
    
    def get_length(self):
        return len(self.value)

def create_required_inputs(value: List[str]):
    output = RequiredInputs(value)
    return output

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic