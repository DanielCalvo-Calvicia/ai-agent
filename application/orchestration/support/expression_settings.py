# ===============================================
#  EXPRESSION SETTINGS
#  The environment variables of the expression flow (the arm gesture that goes with a spoken reply).
# ===============================================

import os
import random
from typing import Optional

EXPRESSION_VARIABLE = "AI_AGENT_EXPRESSION"                       # 1 (default) = gestures on, 0 = off
CHARS_PER_SECOND_VARIABLE = "AI_AGENT_SPEECH_CHARS_PER_SECOND"    # how fast the robot talks, to size the gesture
SEED_VARIABLE = "AI_AGENT_EXPRESSION_SEED"                        # a number makes the gestures repeatable (tests)

DEFAULT_CHARS_PER_SECOND = 14.0
_FALSE = ("0", "false", "no", "off")


def expression_enabled() -> bool:
    return os.environ.get(EXPRESSION_VARIABLE, "1").strip().lower() not in _FALSE


def chars_per_second() -> float:
    try:
        value = float(os.environ.get(CHARS_PER_SECOND_VARIABLE, "") or DEFAULT_CHARS_PER_SECOND)
    except ValueError:
        return DEFAULT_CHARS_PER_SECOND
    return value if value > 0 else DEFAULT_CHARS_PER_SECOND


def speech_seconds(reply: str) -> float:
    """How long the robot takes to say `reply`, from its length."""
    return len(reply.strip()) / chars_per_second()


def new_rng(seed: Optional[str] = None) -> random.Random:
    """The random numbers of a gesture: seeded when the variable (or `seed`) is a number, free otherwise."""
    raw = seed if seed is not None else os.environ.get(SEED_VARIABLE, "")
    try:
        return random.Random(int(raw)) if str(raw).strip() else random.Random()
    except ValueError:
        return random.Random()
