from dataclasses import dataclass

TopPMinValue = 0.0
TopPMaxValue = 1.0

ErrTopPInvalid = ValueError("TopP must be between 0.0 and 1.0")

@dataclass(frozen=True)
class TopP:
    value: float = 1.0
    def __post_init__(self):
        if not TopPMinValue <= self.value <= TopPMaxValue:
            raise ErrTopPInvalid
