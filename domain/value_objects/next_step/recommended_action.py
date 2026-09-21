
from dataclasses import dataclass

ErrRecommendedActionEmpty = ValueError("Recommended action cannot be empty")


@dataclass(frozen=True)
class RecommendedAction:
    value: str

    def validate(self):
        if not self.value or self.value == "":
            raise ErrRecommendedActionEmpty

    def get_value(self):
        return self.value

def create_recommended_action(value: str):
    action = RecommendedAction(value)
    action.validate()
    return action
