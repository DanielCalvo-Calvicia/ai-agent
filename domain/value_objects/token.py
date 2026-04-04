import re
from dataclasses import dataclass, field
from typing import Optional

ErrTokenEmpty = ValueError("Token cannot be empty or whitespace.")

@dataclass(frozen=True)
class Token:
    value: str
    token_type: str = "Bearer"

    def __post_init__(self):
        self.validate()
        object.__setattr__(self, "value", self.value.strip())

    def validate(self):
        if not self.value or self.value.isspace():
            raise ErrTokenEmpty

    def to_header(self) -> str:
        return f"{self.token_type} {self.value}"