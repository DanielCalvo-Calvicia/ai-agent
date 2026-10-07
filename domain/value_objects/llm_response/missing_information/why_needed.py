
from dataclasses import dataclass

ErrWhyNeededEmpty = ValueError("Why needed value cannot be empty.")


@dataclass(frozen=True)
class WhyNeeded:
    value: str

    def validate(self):
        if not self.value.strip():
            raise ErrWhyNeededEmpty
        
    def get_value(self):
        return self.value
        
def create_why_needed(value: str):
    why_needed = WhyNeeded(value)
    why_needed.validate()
    return why_needed
