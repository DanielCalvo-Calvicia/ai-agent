
from dataclasses import dataclass

ErrBlockingNotBoolean = ValueError("Blocking value must be true or false.")


@dataclass(frozen=True)
class Blocking:
    value: bool

    def validate(self):
        if not isinstance(self.value, bool):
            raise ErrBlockingNotBoolean
        
    def get_value(self):
        return self.value
        
def create_blocking(value: bool):
    blocking = Blocking(value)
    blocking.validate()
    return blocking
