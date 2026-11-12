# ===============================================
#  EXPRESSION SETTINGS
#  The environment variables of the expression flow (the arm gesture that goes with a spoken reply): how fast the robot talks and
#  the seed of the random gesture. Whether a reply gets a gesture is the client's choice now: it asks the `gesture` profile (T-05.7).
# ===============================================

import random
from typing import Optional

from application.support.environment import setting

CHARS_PER_SECOND_VARIABLE = "AI_AGENT_SPEECH_CHARS_PER_SECOND"    # how fast the robot talks, to size the gesture
SEED_VARIABLE = "AI_AGENT_EXPRESSION_SEED"                        # a number makes the gestures repeatable (tests)

DEFAULT_CHARS_PER_SECOND = 14.0


def chars_per_second() -> float:
    try:
        value = float(setting(CHARS_PER_SECOND_VARIABLE, "") or DEFAULT_CHARS_PER_SECOND)
    except ValueError:
        return DEFAULT_CHARS_PER_SECOND
    return value if value > 0 else DEFAULT_CHARS_PER_SECOND


def speech_seconds(reply: str) -> float:
    """How long the robot takes to say `reply`, from its length."""
    return len(reply.strip()) / chars_per_second()


def new_rng(seed: Optional[str] = None) -> random.Random:
    """The random numbers of a gesture: seeded when the variable (or `seed`) is a number, free otherwise."""
    raw = seed if seed is not None else setting(SEED_VARIABLE, "")
    try:
        return random.Random(int(raw)) if str(raw).strip() else random.Random()
    except ValueError:
        return random.Random()
