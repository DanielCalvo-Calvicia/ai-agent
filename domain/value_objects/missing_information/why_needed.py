
from dataclasses import dataclass
import json

ErrWhyNeededEmpty = ValueError("Why needed value cannot be empty.")

schema_path = "schema/response/basic/missing_information/missing_information.why_needed.schema.json"

@dataclass(frozen=True)
class WhyNeeded:
    value: str

    def validate(self):
        if not self.value.strip():
            raise ErrWhyNeededEmpty
        
    def get_value(self):
        return self.value
        
def create_why_needed(value: str):
    why_needed = WhyNeeded(value)
    why_needed.validate()
    return why_needed

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic