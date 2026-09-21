
from dataclasses import dataclass

ErrActionIdEmpty = ValueError("Action id cannot be empty")


@dataclass(frozen=True)
class Id:
    value: str

    def validate(self):
        if not self.value or self.value == "":
            raise ErrActionIdEmpty

    def get_value(self):
        return self.value

def create_id(value: str):
    action_id = Id(value)
    action_id.validate()
    return action_id
