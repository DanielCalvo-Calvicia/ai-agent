
from dataclasses import dataclass
from enum import Enum

ErrTypesNotInList = ValueError("Type must be one of analysis, design, generation, modification, validation, classification, orchestration")


class Types(str, Enum):
    ANALYSIS = "analysis"
    DESIGN = "design"
    GENERATION = "generation"
    MODIFICATION = "modification"
    VALIDATION = "validation"
    CLASSIFICATION = "classification"
    ORCHESTRATION = "orchestration"

@dataclass(frozen=True)
class Type:
    value: Types
        
    def get_value(self):
        return self.value.value
        
def get_type_enum(value: str):
    try:
        return Types(value)
    except ValueError:
        raise ErrTypesNotInList
    
def create_type(value: str):
    type_enum = get_type_enum(value)
    type = Type(type_enum)
    return type
