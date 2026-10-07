
from typing import List
from dataclasses import dataclass

ErrActionDependencyIdEmpty = ValueError("Action dependency id cannot be empty.")
ErrActionDependencyAlreadyExists = ValueError("Action dependency already exists.")


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
