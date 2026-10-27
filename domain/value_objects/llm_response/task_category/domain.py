
from dataclasses import dataclass
from enum import Enum

ErrDomainsNotInList = ValueError("domain must be one of SOFTWARE, DATA, WRITING, DESIGN, RESEARCH, OPERATIONS, COMUNICATION, SYSTEM, MOVEMENT")


class Domains(str, Enum):
    SOFTWARE = "software"
    DATA = "data"
    WRITING = "writing"
    DESIGN = "design"
    RESEARCH = "research"
    OPERATIONS = "operations"
    COMUNICATION = "communication"
    SYSTEM = "system"
    MOVEMENT = "movement"

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
