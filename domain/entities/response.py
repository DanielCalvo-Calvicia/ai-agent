from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from domain.entities.action import Action
from domain.entities.tokens_usage import TokensUsage
from domain.value_objects.constraints.constraints import Constraints
from domain.value_objects.intent.intent import Intent
from domain.value_objects.mcp_routing.mcp_routing import MCPRouting
from domain.value_objects.missing_information.missing_information import MissingInformation
from domain.value_objects.next_step.next_step import NextStep
from domain.value_objects.safety_and_validation.safety_and_validation import SafetyAndValidation
from domain.value_objects.task_category.task_category import TaskCategory
from domain.value_objects.user_goal.user_goal import UserGoal


@dataclass
class Response:
    """What one LLM call answered. Structured fields are None when the phase did not produce them."""
    intent: Optional[Intent]
    user_goal: Optional[UserGoal]
    mcp_routing: Optional[MCPRouting]
    task_category: Optional[TaskCategory]
    actions: Optional[List[Action]]
    missing_information: Optional[MissingInformation] = None
    constraints: Optional[Constraints] = None
    safety_and_validation: Optional[SafetyAndValidation] = None
    next_step: Optional[NextStep] = None
    tokens_usage: Optional[TokensUsage] = None
    text: Optional[str] = None
    # The JSON object the LLM answered, for phases whose answer has no domain type.
    raw: Optional[Dict[str, Any]] = None
