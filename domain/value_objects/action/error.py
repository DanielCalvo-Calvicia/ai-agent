
from dataclasses import dataclass
import json

ErrActionErrorEmpty = ValueError("error message cannot be empty.")

schema_path = "schema/response/basic/actions/actions.error.schema.json"

@dataclass(frozen=True)
class Error:
    value: str

    def validate(self): 
        if not self.value or self.value == "":
            raise ErrActionErrorEmpty

    def get_value(self):
        return self.value

def create_error(value: str):
    error = Error(value)
    error.validate()
    return error

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic