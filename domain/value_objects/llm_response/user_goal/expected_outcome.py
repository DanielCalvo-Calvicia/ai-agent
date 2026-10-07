
from dataclasses import dataclass

ErrExpectedOutcomeEmpty = ValueError("Expected outcome cannot be empty")


@dataclass(frozen=True)
class ExpectedOutcome:
    value: str

    def validate(self):
        if not self.value or self.value == "":
            raise ErrExpectedOutcomeEmpty

    def get_value(self):
        return self.value

def create_expected_outcome(value: str):
    expected_outcome = ExpectedOutcome(value)
    expected_outcome.validate()
    return expected_outcome
