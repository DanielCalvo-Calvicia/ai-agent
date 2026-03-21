from dataclasses import dataclass, field
import json

from .domain import Domain, get_domain_enum, create_domain
from .complexity import Complexity, get_complexity_enum, create_complexity
from .type import Type, get_type_enum, create_type

schema_path = "schema/response/task_category/task_category.schema.json"
schema_base_path = "schema/response/task_category/task_category.base.schema.json"

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

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic

def get_base_schema():  
    # Load the base schema from your local file
    with open(schema_base_path + "task_category.base.schema.json", 'r') as f:
        base_schema_dic = json.load(f)
    return base_schema_dic