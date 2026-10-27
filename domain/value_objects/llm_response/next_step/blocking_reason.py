
from dataclasses import dataclass

ErrBlockingReasonEmpty = ValueError("Blocking reason cannot be empty")


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
