
from dataclasses import dataclass
from enum import Enum
import json

ErrComplexityNotInList = ValueError("Complexity must be one of LOW, MEDIUM, HIGH")

schema_path = "schema/response/task_category/task_category.complexity.schema.json"


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

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic