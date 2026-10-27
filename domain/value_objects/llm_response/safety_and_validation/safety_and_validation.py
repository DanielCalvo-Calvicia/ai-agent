from dataclasses import dataclass

from .requires_confirmation import RequiresConfirmation, create_requires_confirmation
from .sensitive import Sensitive, create_sensitive


@dataclass(frozen=True)
class SafetyAndValidation:
    sensitive: Sensitive
    requires_confirmation: RequiresConfirmation

def create_safety_and_validation(sensitive_value: bool, requires_confirmation_value: bool):
    sensitive = create_sensitive(sensitive_value)
    requires_confirmation = create_requires_confirmation(requires_confirmation_value)
    safety_and_validation = SafetyAndValidation(sensitive, requires_confirmation)
    return safety_and_validation
