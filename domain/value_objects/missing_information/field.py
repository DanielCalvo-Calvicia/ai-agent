
from dataclasses import dataclass

ErrFieldEmpty = ValueError("Field value cannot be empty.")


@dataclass(frozen=True)
class Field:
    value: str

    def validate(self):
        if not self.value.strip():
            raise ErrFieldEmpty
        
    def get_value(self):
        return self.value
        
def create_field(value: str):
    field = Field(value)
    field.validate()
    return field
