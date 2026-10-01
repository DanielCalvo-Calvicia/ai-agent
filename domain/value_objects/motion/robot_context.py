from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from domain.value_objects.motion.movement import Movement


@dataclass(frozen=True)
class RobotContext:
    """What motion-flow decided for a message, told to conversation-flow so its reply is truthful.

    `directives` is the accepted movement sequence in execution order. `rejected_reason` says why a
    requested movement cannot be done. Conversation-flow never moves anything and never learns whether
    the movement happened: it only says what the robot is doing, or why it cannot.
    """
    directives: Tuple[Movement, ...] = ()
    rejected_reason: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        """The shape the writer phase reads in its input."""
        return {
            "directives": [{"arm": m.arm, "degrees": m.degrees, "direction": m.direction} for m in self.directives],
            "rejected_reason": self.rejected_reason,
        }
