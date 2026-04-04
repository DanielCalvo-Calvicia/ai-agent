
from dataclasses import dataclass
import json

schema_path = "schema/response/basic/safety_and_validation/safety_and_validation.requires_confirmation.schema.json"

@dataclass(frozen=True)
class RequiresConfirmation:
    value: bool
        
    def get_value(self):
        return self.value
        
def create_requires_confirmation(value: bool):
    requires_confirmation = RequiresConfirmation(value)
    return requires_confirmation

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic

