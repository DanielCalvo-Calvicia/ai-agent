from dataclasses import dataclass, field

from .domain import Domain, get_domain_enum, create_domain
from .complexity import Complexity, get_complexity_enum, create_complexity
from .type import Type, get_type_enum, create_type


@dataclass(frozen=True)
class TaskCategory:
    domain: Domain
    type: Type
    complexity: Complexity
    
def create_task_category(domain_value: str, type_value: str, complexity_value: str):
    domain = create_domain(domain_value)
    type = create_type(type_value)
    complexity = create_complexity(complexity_value)
    task_category = TaskCategory(domain, type, complexity)
    return task_category
