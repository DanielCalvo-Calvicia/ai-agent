# ===============================================
#  GESTURE
#  The arm movements that go with a spoken reply, as the emotion of the conversation asks for them.
#  There is no table "emotion X -> gesture Y": the movements are random. The emotion only shapes the randomness
#  (how big the movements tend to be, how long the pauses between them, whether the other arm answers, which way),
#  and the intensity scales it. The same emotion gives a different gesture every time.
#  Every arm ends where it started, and the way back is part of the time budget, so the gesture lasts about as long as
#  the speech. Pure: the random numbers come from the `rng` the caller gives, so a test can fix them.
# ===============================================

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from domain.value_objects.movement.movement import ARMS, DIRECTIONS, Movement

EMOTIONS = ("joy", "sadness", "anger", "fear", "surprise", "curiosity", "affection", "calm")
DEFAULT_EMOTION = "calm"
INTENSITIES = (1, 2, 3, 4, 5)
DEFAULT_INTENSITY = 3

# What the robot does with a motor: 15 rpm is 90 degrees a second, and every movement costs a little on top (the
# request to the stepper, its start and stop). Measured on the real robot: 180 degrees took about 2.25 seconds.
SPEED_DEGREES_PER_SECOND = 90.0
OVERHEAD_SECONDS = 0.25

MIN_TARGET_SECONDS = 1.5             # even a one-word reply gets a small gesture
TARGET_SPREAD = (0.7, 1.3)           # the gesture lasts about as long as the speech, never exactly
MIN_DEGREES = 5.0
MAX_DEGREES = 360.0                  # one movement
ROUND_TO = 5.0
RETURN_PAUSE = (0.2, 0.6)
IMPROVISED_PAUSE = (0.1, 0.8)
PULL_BACK_FROM = 90.0                # an arm this far from where it started tends to turn back
PULL_BACK_CHANCE = 0.85


@dataclass(frozen=True)
class Profile:
    """The shape of the randomness of one emotion (ranges, not recipes).

    degrees: the size of one movement at intensity 3; pause: seconds between movements; both_arms: the chance that
    the other arm moves next; reverse: the chance a movement goes the other way.
    """
    degrees: Tuple[float, float]
    pause: Tuple[float, float]
    both_arms: float
    reverse: float


PROFILES: Dict[str, Profile] = {
    "joy": Profile((40, 160), (0.1, 0.8), 0.6, 0.4),
    "sadness": Profile((15, 60), (0.8, 2.2), 0.2, 0.7),
    "anger": Profile((60, 180), (0.05, 0.4), 0.5, 0.5),
    "fear": Profile((20, 70), (0.05, 0.5), 0.5, 0.5),
    "surprise": Profile((60, 150), (0.2, 1.0), 0.7, 0.3),
    "curiosity": Profile((20, 90), (0.4, 1.5), 0.1, 0.5),
    "affection": Profile((20, 80), (0.5, 1.6), 0.7, 0.4),
    "calm": Profile((10, 45), (0.8, 2.0), 0.3, 0.5),
}
SIZE_BY_INTENSITY = {1: 0.5, 2: 0.75, 3: 1.0, 4: 1.25, 5: 1.5}
PAUSE_BY_INTENSITY = {1: 1.15, 2: 0.95, 3: 0.8, 4: 0.65, 5: 0.55}


def movement_seconds(degrees: float) -> float:
    """How long a movement takes the motor."""
    return degrees / SPEED_DEGREES_PER_SECOND + OVERHEAD_SECONDS


def gesture_seconds(movements: Sequence[Movement]) -> float:
    """How long a gesture lasts, pauses included."""
    return sum(movement.pause_seconds + movement_seconds(abs(movement.degrees)) for movement in movements)


def net_rotation(movements: Sequence[Movement], arm: str) -> float:
    """Where the arm ends relative to where it started: forward counts up, reverse counts down."""
    total = 0.0
    for movement in movements:
        if movement.arm == arm:
            total += abs(movement.degrees) if movement.direction == "forward" else -abs(movement.degrees)
    return total


def _rounded(degrees: float) -> float:
    return max(MIN_DEGREES, min(MAX_DEGREES, round(degrees / ROUND_TO) * ROUND_TO))


def _clean(movement: Movement) -> Movement | None:
    """An improvised movement as a gesture can use it, or None when it is not usable (unknown arm, no number...)."""
    if movement.arm not in ARMS or movement.direction not in DIRECTIONS:
        return None
    if not math.isfinite(movement.degrees) or movement.degrees == 0:
        return None
    return Movement(arm=movement.arm, degrees=min(abs(movement.degrees), MAX_DEGREES), direction=movement.direction)


class _Way:
    """How far each arm is from where it started, and what bringing both back costs."""

    def __init__(self) -> None:
        self.net: Dict[str, float] = {arm: 0.0 for arm in ARMS}

    def moved(self, arm: str, degrees: float, direction: str) -> None:
        self.net[arm] += degrees if direction == "forward" else -degrees

    def after(self, arm: str, degrees: float, direction: str) -> "_Way":
        other = _Way()
        other.net = dict(self.net)
        other.moved(arm, degrees, direction)
        return other

    def back_movements(self) -> int:
        return sum(math.ceil(abs(value) / MAX_DEGREES) for value in self.net.values() if abs(value) >= 1.0)

    def back_degrees(self) -> float:
        return sum(abs(value) for value in self.net.values() if abs(value) >= 1.0)

    def back_seconds(self) -> float:
        mean_pause = sum(RETURN_PAUSE) / 2
        return sum(OVERHEAD_SECONDS + mean_pause + abs(value) / SPEED_DEGREES_PER_SECOND
                   for value in self.net.values() if abs(value) >= 1.0)


def build_gesture(
    emotion: str,
    intensity: int,
    improvised: Sequence[Movement],
    speech_seconds: float,
    rng: random.Random,
    *,
    max_movements: int,
    max_total_degrees: float,
) -> List[Movement]:
    """
    The movements of a gesture: random, shaped by the emotion, lasting about as long as the speech.

    `improvised` are movements the model suggested; the usable ones are kept and mixed in at random places.
    Every arm ends where it started. The result never has more than `max_movements` movements or more than
    `max_total_degrees` degrees in all, so the validator that checks it afterwards has nothing to refuse.
    """
    profile = PROFILES.get(emotion, PROFILES[DEFAULT_EMOTION])
    level = intensity if intensity in INTENSITIES else DEFAULT_INTENSITY
    size = SIZE_BY_INTENSITY[level]
    pause_scale = PAUSE_BY_INTENSITY[level]

    target = max(MIN_TARGET_SECONDS, speech_seconds * rng.uniform(*TARGET_SPREAD))

    # The model's own ideas come first in the budget, as long as they leave room for the way back.
    way = _Way()
    extras: List[Movement] = []
    elapsed = 0.0
    total = 0.0
    for extra in (clean for clean in (_clean(movement) for movement in improvised) if clean is not None):
        after = way.after(extra.arm, extra.degrees, extra.direction)
        if (len(extras) + 1 + after.back_movements() > max_movements
                or total + extra.degrees + after.back_degrees() > max_total_degrees):
            continue
        extras.append(extra)
        way = after
        elapsed += movement_seconds(extra.degrees)
        total += extra.degrees

    generated: List[Movement] = []
    arm = rng.choice(ARMS)
    while True:
        pause = 0.0 if not generated else round(rng.uniform(*profile.pause) * pause_scale, 2)
        direction = _direction(way, arm, profile, rng)
        degrees = _rounded(rng.uniform(*profile.degrees) * size)
        while degrees >= MIN_DEGREES:                                # the biggest size that still fits
            after = way.after(arm, degrees, direction)
            fits = (
                len(extras) + len(generated) + 1 + after.back_movements() <= max_movements
                and total + degrees + after.back_degrees() <= max_total_degrees
                and elapsed + pause + movement_seconds(degrees) + after.back_seconds() <= target
            )
            if fits:
                break
            degrees -= ROUND_TO
        else:
            break                                                    # nothing fits any more: the gesture is done
        generated.append(Movement(arm=arm, degrees=degrees, direction=direction, pause_seconds=pause))
        way = way.after(arm, degrees, direction)
        elapsed += pause + movement_seconds(degrees)
        total += degrees
        if rng.random() < profile.both_arms:
            arm = ARMS[1] if arm == ARMS[0] else ARMS[0]

    movements = generated
    for extra in extras:                                             # the model's own ideas, anywhere in the gesture
        position = rng.randint(0, len(movements))
        movements = (movements[:position]
                     + [Movement(extra.arm, extra.degrees, extra.direction, round(rng.uniform(*IMPROVISED_PAUSE), 2))]
                     + movements[position:])
    if movements:                                                    # the gesture starts with the speech
        first = movements[0]
        movements[0] = Movement(first.arm, first.degrees, first.direction, 0.0)

    return movements + _returns(movements, rng)


def _direction(way: _Way, arm: str, profile: Profile, rng: random.Random) -> str:
    """Forward or reverse: the emotion's own taste, unless the arm has gone far and tends to turn back."""
    if abs(way.net[arm]) >= PULL_BACK_FROM and rng.random() < PULL_BACK_CHANCE:
        return "reverse" if way.net[arm] > 0 else "forward"
    return "reverse" if rng.random() < profile.reverse else "forward"


def _returns(movements: Sequence[Movement], rng: random.Random) -> List[Movement]:
    """The movements that bring every arm back to where it started."""
    back: List[Movement] = []
    for arm in ARMS:
        remaining = net_rotation(movements, arm)
        while abs(remaining) >= 1.0:
            step = min(abs(remaining), MAX_DEGREES)
            direction = "reverse" if remaining > 0 else "forward"
            back.append(Movement(arm, step, direction, round(rng.uniform(*RETURN_PAUSE), 2)))
            remaining += -step if remaining > 0 else step
    return back
