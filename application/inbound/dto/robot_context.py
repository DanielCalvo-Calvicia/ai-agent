from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict

from domain.value_objects.motion.movement import Movement
from domain.value_objects.motion.robot_context import RobotContext


class MovementDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arm: Literal["left", "right"]
    degrees: float
    direction: Literal["forward", "reverse"] = "forward"


class RobotContextDTO(BaseModel):
    """What motion-flow decided for the message (sent by Brain to conversation-flow)."""
    model_config = ConfigDict(extra="forbid")

    directives: List[MovementDTO] = []
    rejected_reason: Optional[str] = None

    def to_domain(self) -> RobotContext:
        return RobotContext(
            directives=tuple(Movement(arm=d.arm, degrees=d.degrees, direction=d.direction) for d in self.directives),
            rejected_reason=self.rejected_reason,
        )
