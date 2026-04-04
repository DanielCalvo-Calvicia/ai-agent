
from dataclasses import dataclass
import json

ErrBlockingReasonEmpty = ValueError("Blocking reason cannot be empty")

schema_path = "schema/response/basic/next_step/next_step.blocking_reason.schema.json"

@dataclass(frozen=True)
class BlockingReason:
    value: str

    def validate(self):
        if not self.value or self.value == "":
            raise ErrBlockingReasonEmpty

    def get_value(self):
        return self.value

def create_blocking_reason(value: str):
    reason = BlockingReason(value)
    reason.validate()
    return reason

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic