
from dataclasses import dataclass


@dataclass(frozen=True)
class RequiresConfirmation:
    value: bool
        
    def get_value(self):
        return self.value
        
def create_requires_confirmation(value: bool):
    requires_confirmation = RequiresConfirmation(value)
    return requires_confirmation
