
from dataclasses import dataclass

ErrSummaryEmpty = ValueError("Summary cannot be empty")


@dataclass(frozen=True)
class Summary:
    value: str

    def validate(self):
        if not self.value or self.value == "":
            raise ErrSummaryEmpty

    def get_value(self):
        return self.value

def create_summary(value: str):
    summary = Summary(value)
    summary.validate()
    return summary
