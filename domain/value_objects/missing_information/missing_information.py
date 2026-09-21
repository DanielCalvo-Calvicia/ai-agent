
from dataclasses import dataclass

from .field import Field, create_field
from .why_needed import WhyNeeded, create_why_needed
from .blocking import Blocking, create_blocking


@dataclass(frozen=True)
class MissingInformation:
    field: Field
    why_needed: WhyNeeded
    blocking: Blocking
        
    def get_field(self):
        return self.field.get_value()
    def get_why_needed(self):
        return self.why_needed.get_value()
    def get_blocking(self):
        return self.blocking.get_value()
        
        
def create_missing_information(field_value: str, why_needed_value: str, blocking_value: str):
    field = create_field(field_value)
    why_needed = create_why_needed(why_needed_value)
    blocking = create_blocking(blocking_value)
    missing_information = MissingInformation(field, why_needed, blocking)
    return missing_information
