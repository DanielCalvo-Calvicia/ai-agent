from dataclasses import dataclass

ARMS = ("left", "right")
DIRECTIONS = ("forward", "reverse")


@dataclass(frozen=True)
class Movement:
    """One arm movement of a sequence: which arm, how many degrees, and in which direction.

    `degrees` is signed, so "left 90" followed by "left -90" brings the arm back.
    """
    arm: str
    degrees: float
    direction: str = "forward"
