
from dataclasses import dataclass
from enum import Enum

ErrStatusNotInList = ValueError("status must be one of PROCEED, AWAITING_USER_INPUT, AWAITING_CONFIRMATION, RETRY, ERROR, COMPLETE")


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
