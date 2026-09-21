
from dataclasses import dataclass


@dataclass(frozen=True)
class Sensitive:
    value: bool
        
    def get_value(self):
        return self.value
        
def create_sensitive(value: bool):
    sensitive = Sensitive(value)
    return sensitive
