# ===============================================
#  ROBOT DIRECTIVE
#  Reads the finished action tree for a movement request. ai-agent never
#  moves anything itself: this only turns a successful "robot_action" into
#  a plain, typed value Brain can decide to act on.
# ===============================================

import re
from dataclasses import dataclass
from typing import List, Optional

from domain.entities.action import Action

ROBOT_ACTION_TYPE = "robot_action"

# The cognitive worker (phase 4) is instructed to answer a robot_action with exactly this
# shape (see prompts/advanced/4_cognitive_worker.txt). Anything else is treated as no directive.
_PATTERN = re.compile(
    r"^arm=(?P<arm>left|right)\s+degrees=(?P<degrees>-?\d+(?:\.\d+)?)\s+direction=(?P<direction>forward|reverse)$"
)


@dataclass(frozen=True)
class RobotDirective:
    arm: str
    degrees: float
    direction: str


def find_directive(actions: Optional[List[Action]]) -> Optional[RobotDirective]:
    """The first successful robot_action in the tree (plan order), or None."""
    for action in _flatten(actions or []):
        if not action.action_type or action.action_type.get_value() != ROBOT_ACTION_TYPE:
            continue
        if not action.is_successful() or not action.output:
            continue
        match = _PATTERN.match(action.output.get_value().strip())
        if not match:
            continue
        return RobotDirective(
            arm=match.group("arm"),
            degrees=float(match.group("degrees")),
            direction=match.group("direction"),
        )
    return None


def _flatten(actions: List[Action]) -> List[Action]:
    flat: List[Action] = []
    for action in actions:
        flat.append(action)
        if action.subactions:
            flat.extend(_flatten(list(action.subactions.values())))
    return flat
