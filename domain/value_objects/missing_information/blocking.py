
from dataclasses import dataclass

ErrBlockingEmpty = ValueError("Blocking value cannot be empty.")


@dataclass(frozen=True)
class Blocking:
    value: str

    def validate(self):
        if not self.value.strip():
            raise ErrBlockingEmpty
        
    def get_value(self):
        return self.value
        
def create_blocking(value: str):
    blocking = Blocking(value)
    blocking.validate()
    return blocking
