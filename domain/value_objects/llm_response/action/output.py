
from dataclasses import dataclass

ErrActionOutputEmpty = ValueError("Action output cannot be empty")


@dataclass(frozen=True)
class Output:
    value: str

    def validate(self):
        if not self.value or self.value == "":
            raise ErrActionOutputEmpty

    def get_value(self):
        return self.value

def create_output(value: str):
    output = Output(value)
    output.validate()
    return output
