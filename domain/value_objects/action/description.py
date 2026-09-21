
from dataclasses import dataclass

ErrActionDescriptionEmpty = ValueError("Action description cannot be empty")


@dataclass(frozen=True)
class Description:
    value: str

    def validate(self):
        if not self.value or self.value == "":
            raise ErrActionDescriptionEmpty

    def get_value(self):
        return self.value

def create_description(value: str):
    description = Description(value)
    description.validate()
    return description
