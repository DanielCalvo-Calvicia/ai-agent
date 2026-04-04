from dataclasses import dataclass, field
from typing import Optional, Self

# Assuming the Value Objects we created previously
from domain.value_objects.token import Token
from domain.value_objects.email import Email
from domain.value_objects.password import Password

@dataclass(frozen=True) # Immutability prevents accidental side-effects
class User:
    id: int
    email: Email
    hashed_password: Password
    is_active: bool = False
    token: Optional[Token] = field(default=None)

    def deactivate(self) -> Self:
        """Domain logic to handle user deactivation."""
        return self._replace(is_active=False, token=None)

    def update_email(self, new_email: Email) -> Self:
        """Ensures email updates go through the Value Object validation."""
        return self._replace(email=new_email)

    def verify_password(self, plain_password: str) -> bool:
        """
        Logic for password verification would go here, 
        abstracting the hashing check away from the service layer.
        """
        # Example placeholder: return hash_provider.verify(plain_password, self.hashed_password.value)
        return False

    def _replace(self, **changes) -> Self:
        """Helper to return a new instance with updated fields (Functional approach)."""
        from dataclasses import replace
        return replace(self, **changes)