from dataclasses import dataclass, field
from typing import Any, Dict, List

MinConfidence = 0.0
MaxConfidence = 1.0

DefaultThresholdConfidence = 0.75

ErrConfidencePrimaryEmpty = ValueError("Primary intent cannot be empty.")
ErrConfidenceNotNumber = lambda confidence: ValueError(f"Confidence {confidence} must be a number.")
ErrConfidenceBetweenMinMax = lambda confidence: ValueError(f"Confidence {confidence} must be between {MinConfidence} and {MaxConfidence}.")


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
