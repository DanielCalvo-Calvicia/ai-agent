
from typing import List
from dataclasses import dataclass
import json

from domain.value_objects.action.dependencies import Dependencies

ErrRequestUserInputEmpty = ValueError("Request user input cannot be empty.")
ErrRequestUserInputAlreadyExists = ValueError("Request user input already exists.")

schema_path = "schema/response/actions/next_step.request_user_input.schema.json"

@dataclass(frozen=True)
class RequestUserInput:
    value: List[str]

    def validate(self):
        if not self.value or self.value == []:
            raise ErrRequestUserInputEmpty

    def add_input(self, input_value: str):
        if not input_value.strip():
            raise ErrRequestUserInputEmpty
        if input_value in self.value:
            raise ErrRequestUserInputAlreadyExists
        new_inputs = self.value + [input_value]
        object.__setattr__(self, "value", new_inputs)

    def get_value(self):
        return self.value
    
    def get_length(self):
        return len(self.value)

def create_request_user_input(value: List[str]):
    request_user_input = RequestUserInput(value)
    request_user_input.validate()
    return request_user_input

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic