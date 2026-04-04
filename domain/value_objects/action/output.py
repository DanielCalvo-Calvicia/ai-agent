
from dataclasses import dataclass
import json

ErrActionOutputEmpty = ValueError("Action output cannot be empty")

schema_path = "schema/response/basic/actions/actions.output.schema.json"

@dataclass(frozen=True)
class Output:
    value: str

    def validate(self):
        if not self.value or self.value == "":
            raise ErrActionOutputEmpty

    def get_value(self):
        return self.value

def create_output(value: str):
    output = Output(value)
    output.validate()
    return output

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic