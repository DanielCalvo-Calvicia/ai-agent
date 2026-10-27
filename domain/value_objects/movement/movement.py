from dataclasses import dataclass

ARMS = ("left", "right")
DIRECTIONS = ("forward", "reverse")


@dataclass(frozen=True)
class Movement:
    """One arm movement of a sequence: which arm, how many degrees, and in which direction.

    `degrees` is signed, so "left 90" followed by "left -90" brings the arm back.
    `pause_seconds` is how long to wait after the previous movement ends before this one starts (0 = at once);
    only an expressive gesture uses it.
    """
    arm: str
    degrees: float
    direction: str = "forward"
    pause_seconds: float = 0.0
