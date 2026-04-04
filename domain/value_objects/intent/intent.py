from dataclasses import dataclass, field
import json
from typing import Any, Dict, List

MinConfidence = 0.0
MaxConfidence = 1.0

DefaultThresholdConfidence = 0.75

ErrConfidencePrimaryEmpty = ValueError("Primary intent cannot be empty.")
ErrConfidenceNotNumber = lambda confidence: ValueError(f"Confidence {confidence} must be a number.")
ErrConfidenceBetweenMinMax = lambda confidence: ValueError(f"Confidence {confidence} must be between {MinConfidence} and {MaxConfidence}.")

schema_full_path = "schema/response/advanced/intent/intent.schema.json"
schema_base_path = "schema/response/advanced/intent/intent.base.schema.json"
schema_confidence_path = "schema/response/advanced/intent/intent.confidence.schema.json"
schema_primary_path = "schema/response/advanced/intent/intent.primary.schema.json"
schema_secondary_path = "schema/response/advanced/intent/intent.secondary.schema.json"


@dataclass(frozen=True)
class Intent:
    primary: str
    secondary: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def __post_init__(self):
        self.validate()

        object.__setattr__(self, "primary", str(self.primary))
        object.__setattr__(self, "secondary", tuple(self.secondary))
        object.__setattr__(self, "confidence", float(self.confidence))

    def validate(self):
        self._validate_primary()
        self._validate_confidence()

    def _validate_primary(self):
        if self.primary == "":
            raise ErrConfidencePrimaryEmpty
    def _validate_confidence(self):
        if not isinstance(self.confidence, (int, float)):
            raise ErrConfidenceNotNumber(self.confidence)

        if not (MinConfidence <= float(self.confidence) <= MaxConfidence):
            raise ErrConfidenceBetweenMinMax(self.confidence)

    def is_high_confidence(self, threshold: float = DefaultThresholdConfidence) -> bool:
        return self.confidence >= threshold
    
def create_intent(primary: str, secondary: List[str], confidence: float):
    intent = Intent(primary, secondary, confidence)
    intent.validate()
    return intent

def get_schema():
    # Load the schema from your local file
    with open(schema_full_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic

def get_base_schema():
    # Load the base schema from your local file
    with open(schema_base_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic

def get_confidence_schema():
    # Load the confidence schema from your local file
    with open(schema_confidence_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic

def get_primary_schema():
    # Load the primary schema from your local file
    with open(schema_primary_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic

def get_secondary_schema():
    # Load the secondary schema from your local file
    with open(schema_secondary_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic

