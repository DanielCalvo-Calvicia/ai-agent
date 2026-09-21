
from typing import List
from dataclasses import dataclass

from domain.value_objects.action.dependencies import Dependencies

ErrRequestedUserInputEmpty = ValueError("Request user input cannot be empty.")
ErrRequestedUserInputAlreadyExists = ValueError("Request user input already exists.")


@dataclass(frozen=True)
class RequestedUserInput:
    value: List[str]

    def validate(self):
        if not self.value or self.value == []:
            raise ErrRequestedUserInputEmpty

    def add_input(self, input_value: str):
        if not input_value.strip():
            raise ErrRequestedUserInputEmpty
        if input_value in self.value:
            raise ErrRequestedUserInputAlreadyExists
        new_inputs = self.value + [input_value]
        object.__setattr__(self, "value", new_inputs)

    def get_value(self):
        return self.value
    
    def get_length(self):
        return len(self.value)

def create_requested_user_input(value: List[str]):
    requested_user_input = RequestedUserInput(value)
    requested_user_input.validate()
    return requested_user_input
