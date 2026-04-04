
from typing import List
from dataclasses import dataclass
import json

ErrActionDependencyIdEmpty = ValueError("Action dependency id cannot be empty.")
ErrActionDependencyAlreadyExists = ValueError("Action dependency already exists.")

schema_path = "schema/response/basic/actions/actions.action_type.schema.json"

@dataclass(frozen=True)
class Dependencies:
    value: List[str]


    def add_dependency(self, dependency_id: str):
        if not dependency_id.strip():
            raise ErrActionDependencyIdEmpty
        if dependency_id in self.value:
            raise ErrActionDependencyAlreadyExists
        new_dependencies = self.value + [dependency_id]
        object.__setattr__(self, "value", new_dependencies)

    def get_value(self):
        return self.value
    
    def get_length(self):
        return len(self.value)

def create_dependencies(value: List[str]):
    dependencies = Dependencies(value)
    return dependencies

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic