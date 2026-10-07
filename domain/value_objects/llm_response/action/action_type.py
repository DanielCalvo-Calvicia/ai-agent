
from dataclasses import dataclass

ErrActionTypeEmpty = ValueError("Action type cannot be empty")


@dataclass(frozen=True)
class ActionType:
    value: str

    def validate(self):
        if not self.value or self.value == "":
            raise ErrActionTypeEmpty

    def get_value(self):
        return self.value

def create_action_type(value: str):
    action_type = ActionType(value)
    action_type.validate()
    return action_type
