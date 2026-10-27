
from dataclasses import dataclass
from typing import List

ErrActionRequiredInputEmpty = ValueError("Required input name cannot be empty.")


@dataclass(frozen=True)
class RequiredInputs:
    value: List[str]

    def validate(self):
        if not self.value or self.value == []:
            raise ErrActionRequiredInputEmpty

    def add_required_input(self, input_name: str):
        if not input_name.strip():
            raise ErrActionRequiredInputEmpty
        new_required_inputs = self.value + [input_name]
        object.__setattr__(self, "value", new_required_inputs)

    def get_value(self):
        return self.value
    
    def get_length(self):
        return len(self.value)

def create_required_inputs(value: List[str]):
    output = RequiredInputs(value)
    return output
