from dataclasses import dataclass

ErrTokensNegative = ValueError("Max tokens cannot be negative")

@dataclass(frozen=True)
class MaxTokens:
    value: int

    def __post_init__(self):
        """
        Ensures that the max tokens value is not negative.

        Raises:
            ErrTokensNegative: If the max tokens value is negative.
        """
        if self.value < 0:
            raise ErrTokensNegative

def create_max_tokens(value: int) -> MaxTokens:
    return MaxTokens(value)
