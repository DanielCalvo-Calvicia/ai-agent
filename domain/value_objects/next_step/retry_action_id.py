
from dataclasses import dataclass
import json

ErrRetryActionIdEmpty = ValueError("Retry action id cannot be empty")

schema_path = "schema/response/basic/actions/next_step.retry_action_id.schema.json"

@dataclass(frozen=True)
class RetryActionId:
    value: str

    def validate(self):
        if not self.value or self.value == "":
            raise ErrRetryActionIdEmpty

    def get_value(self):
        return self.value

def create_retry_action_id(value: str):
    retry_action_id = RetryActionId(value)
    retry_action_id.validate()
    return retry_action_id

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic