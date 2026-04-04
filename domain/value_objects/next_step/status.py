
from dataclasses import dataclass
from enum import Enum
import json

ErrStatusNotInList = ValueError("status must be one of PROCEED, AWAITING_USER_INPUT, AWAITING_CONFIRMATION, RETRY, ERROR, COMPLETE")

schema_path = "schema/response/basic/missing_information/missing_information.status.schema.json"


class Statuses(str, Enum):
    PROCEED = "proceed"
    AWAITING_USER_INPUT = "awaiting_user_input"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    RETRY = "retry"
    ERROR = "error"
    COMPLETE = "complete"

@dataclass(frozen=True)
class Status:
    value: Statuses
        
    def get_value(self):
        return self.value.value
        
def get_status_enum(value: str):
    try:
        return Statuses(value)
    except ValueError:
        raise ErrStatusNotInList
    
def create_status(value: str):
    status_enum = get_status_enum(value)
    status = Status(status_enum)
    return status

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic