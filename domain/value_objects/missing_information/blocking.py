
from dataclasses import dataclass
import json

ErrBlockingEmpty = ValueError("Blocking value cannot be empty.")

schema_path = "schema/response/basic/missing_information/missing_information.blocking.schema.json"

@dataclass(frozen=True)
class Blocking:
    value: str

    def validate(self):
        if not self.value.strip():
            raise ErrBlockingEmpty
        
    def get_value(self):
        return self.value
        
def create_blocking(value: str):
    blocking = Blocking(value)
    blocking.validate()
    return blocking

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic

