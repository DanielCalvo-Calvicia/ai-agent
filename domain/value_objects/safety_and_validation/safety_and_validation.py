from dataclasses import dataclass
import json

from .requires_confirmation import RequiresConfirmation, create_requires_confirmation
from .sensitive import Sensitive, create_sensitive

schema_path = "schema/response/safety_and_validation/safety_and_validation.schema.json"
schema_base_path = "schema/response/safety_and_validation/"

@dataclass(frozen=True)
class SafetyAndValidation:
    sensitive: Sensitive
    requires_confirmation: RequiresConfirmation

def create_safety_and_validation(sensitive_value: bool, requires_confirmation_value: bool):
    sensitive = create_sensitive(sensitive_value)
    requires_confirmation = create_requires_confirmation(requires_confirmation_value)
    safety_and_validation = SafetyAndValidation(sensitive, requires_confirmation)
    return safety_and_validation

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic
def get_base_schema():
    # Load the base schema from your local file
    with open(schema_base_path + "safety_and_validation.base.schema.json", 'r') as f:
        base_schema_dic = json.load(f)
    return base_schema_dic