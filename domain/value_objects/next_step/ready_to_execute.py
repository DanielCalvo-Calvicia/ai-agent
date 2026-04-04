
from dataclasses import dataclass
import json

schema_path = "schema/response/basic/missing_information/next_step.ready_to_execute.schema.json"

@dataclass(frozen=True)
class ReadyToExecute:
    value: bool
        
    def get_value(self):
        return self.value
        
def create_ready_to_execute(value: bool):
    ready_to_execute = ReadyToExecute(value)
    return ready_to_execute

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic