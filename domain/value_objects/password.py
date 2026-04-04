import re
from dataclasses import dataclass, field
from typing import Optional

MIN_PASSWORD_LENGTH = 8

ErrPasswordTooShort = ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")

@dataclass(frozen=True)
class Password:
    value: str

    def __post_init__(self):
        self.validate()

    def validate(self):
        if len(self.value) < MIN_PASSWORD_LENGTH:
            raise ErrPasswordTooShort

    def __str__(self) -> str:
        return "********"  # Prevent accidental logging of raw password