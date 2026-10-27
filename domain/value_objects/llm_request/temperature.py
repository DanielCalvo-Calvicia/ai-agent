from dataclasses import dataclass

MinTemperature = 0.0
MaxTemperature = 1.0

ErrTemperatureInvalid = ValueError("Temperature must be between 0.0 and 1.0")

@dataclass(frozen=True)
class Temperature:
    value: float

    def __post_init__(self):
        if self.value < MinTemperature or self.value > MaxTemperature:
            raise ErrTemperatureInvalid
        
def create_temperature(value: float) -> Temperature:
    return Temperature(value)
