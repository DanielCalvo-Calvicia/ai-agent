
from dataclasses import dataclass
from enum import Enum

ErrComplexityNotInList = ValueError("Complexity must be one of LOW, MEDIUM, HIGH")


class Complexities(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

@dataclass(frozen=True)
class Complexity:
    value: Complexities
        
    def get_value(self):
        return self.value.value
        
def get_complexity_enum(value: str):
    try:
        return Complexities(value)
    except ValueError:
        raise ErrComplexityNotInList
    
def create_complexity(value: str):
    complexity_enum = get_complexity_enum(value)
    complexity = Complexity(complexity_enum)
    return complexity
