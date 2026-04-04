from enum import Enum
from dataclasses import dataclass
from typing import Dict


class ReasoningEffort(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    

ErrInvalidEffort = ValueError("Invalid effort")

@dataclass(frozen=True)
class ReasoningConfig:
    effort: ReasoningEffort

    def __post_init__(self):
        if self.effort not in ReasoningEffort:
            raise ErrInvalidEffort

    def to_dict(self) -> dict:
        return {"effort": self.effort.value}

def create_reasoning_config(effort: ReasoningEffort) -> ReasoningConfig:
    return ReasoningConfig(effort=effort)