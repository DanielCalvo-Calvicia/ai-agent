
from dataclasses import dataclass
import json

ErrFieldEmpty = ValueError("Field value cannot be empty.")

schema_path = "schema/response/basic/missing_information/missing_information.field.schema.json"

@dataclass(frozen=True)
class Field:
    value: str

    def validate(self):
        if not self.value.strip():
            raise ErrFieldEmpty
        
    def get_value(self):
        return self.value
        
def create_field(value: str):
    field = Field(value)
    field.validate()
    return field

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic
