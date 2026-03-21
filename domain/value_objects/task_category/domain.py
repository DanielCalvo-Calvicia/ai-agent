
from dataclasses import dataclass
from enum import Enum
import json

ErrDomainsNotInList = ValueError("domain must be one of SOFTWARE, DATA, WRITING, DESIGN, RESEARCH, OPERATIONS, COMUNICATION, SYSTEM")

schema_path = "schema/response/task_category/task_category.domain.schema.json"


class Domains(str, Enum):
    SOFTWARE = "software"
    DATA = "data"
    WRITING = "writing"
    DESIGN = "design"
    RESEARCH = "research"
    OPERATIONS = "operations"
    COMUNICATION = "communication"
    SYSTEM = "system"

@dataclass(frozen=True)
class Domain:
    value: Domains
        
    def get_value(self):
        return self.value.value
        
def get_domain_enum(value: str):
    try:
        return Domains(value)
    except ValueError:
        raise ErrDomainsNotInList
    
def create_domain(value: str):
    domain_enum = get_domain_enum(value)
    domain = Domain(domain_enum)
    return domain

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic