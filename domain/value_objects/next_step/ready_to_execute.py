
from dataclasses import dataclass


@dataclass(frozen=True)
class ReadyToExecute:
    value: bool
        
    def get_value(self):
        return self.value
        
def create_ready_to_execute(value: bool):
    ready_to_execute = ReadyToExecute(value)
    return ready_to_execute
