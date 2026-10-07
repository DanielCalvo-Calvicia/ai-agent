
from dataclasses import dataclass

ErrRetryActionIdEmpty = ValueError("Retry action id cannot be empty")


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
