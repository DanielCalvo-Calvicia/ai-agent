
from dataclasses import dataclass

ErrActionErrorEmpty = ValueError("error message cannot be empty.")


@dataclass(frozen=True)
class Error:
    value: str

    def validate(self): 
        if not self.value or self.value == "":
            raise ErrActionErrorEmpty

    def get_value(self):
        return self.value

def create_error(value: str):
    error = Error(value)
    error.validate()
    return error
