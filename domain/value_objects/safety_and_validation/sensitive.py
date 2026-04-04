
from dataclasses import dataclass
import json

schema_path = "schema/response/basic/safety_and_validation/safety_and_validation.sensitive.schema.json"

@dataclass(frozen=True)
class Sensitive:
    value: bool
        
    def get_value(self):
        return self.value
        
def create_sensitive(value: bool):
    sensitive = Sensitive(value)
    return sensitive


def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic

