import re
from dataclasses import dataclass, field
from typing import Optional

ErrEmailInvalid = lambda email: ValueError(f"'{email}' is not a valid email address.")

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

@dataclass(frozen=True)
class Email:
    address: str

    def __post_init__(self):
        self.validate()
        # Normalize: strip whitespace and lowercase
        object.__setattr__(self, "address", self.address.strip().lower())

    def validate(self):
        if not EMAIL_REGEX.match(self.address):
            raise ErrEmailInvalid(self.address)

    @property
    def domain(self) -> str:
        return self.address.split('@')[-1]