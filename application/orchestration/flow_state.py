# ===============================================
#  FLOW STATE
#  Everything the phases read and write while one
#  user message travels through the pipeline.
# ===============================================

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from domain.entities.action import Action
from domain.entities.response import Response
from domain.value_objects.constraints.constraints import Constraints
from domain.value_objects.intent.intent import Intent
from domain.value_objects.mcp_routing.mcp_routing import MCPRouting
from domain.value_objects.message import Message
from domain.value_objects.missing_information.missing_information import MissingInformation
from domain.value_objects.next_step.next_step import NextStep, create_next_step
from domain.value_objects.safety_and_validation.safety_and_validation import SafetyAndValidation, create_safety_and_validation
from domain.value_objects.task_category.task_category import TaskCategory
from domain.value_objects.user_goal.user_goal import UserGoal


@dataclass
class FlowState:
    message: str
    intent: Optional[Intent] = None
    user_goal: Optional[UserGoal] = None
    mcp_routing: Optional[MCPRouting] = None
    task_category: Optional[TaskCategory] = None
    actions: Optional[List[Action]] = None
    missing_information: Optional[MissingInformation] = None
    constraints: Optional[Constraints] = None
    safety_and_validation: Optional[SafetyAndValidation] = None
    next_step: Optional[NextStep] = None
    # Earlier turns of the session (oldest first). Read by triage and the project manager.
    history: List[Message] = field(default_factory=list)
    # What the user said when the flow stopped to ask: (question, answer), oldest first.
    answers: List[Tuple[str, str]] = field(default_factory=list)

    def history_as_dicts(self) -> List[dict]:
        return [{"role": m.role.value, "content": m.content} for m in self.history]

    def answers_as_dicts(self) -> List[dict]:
        return [{"question": question, "answer": answer} for question, answer in self.answers]

    def add_answer(self, question: str, answer: str) -> None:
        self.answers.append((question, answer))

    def message_with_history(self) -> str:
        """The user message, with the earlier turns before it and the answers the user gave after it."""
        text = self.message

        if self.history:
            turns = "\n".join(f"{m.role.value}: {m.content}" for m in self.history)
            text = f"Conversation so far:\n{turns}\n\nCurrent user message:\n{self.message}"

        if self.answers:
            given = "\n".join(f"- Asked: {question} Answer: {answer}" for question, answer in self.answers)
            text = f"{text}\n\nInformation the user gave when asked:\n{given}"

        return text

    def confirm(self) -> None:
        """The user agreed: nothing needs confirmation any more and the flow can go on."""
        sensitive = bool(
            self.safety_and_validation
            and self.safety_and_validation.sensitive
            and self.safety_and_validation.sensitive.get_value()
        )
        self.safety_and_validation = create_safety_and_validation(
            sensitive_value=sensitive, requires_confirmation_value=False)
        self.next_step = create_next_step(
            ready_to_execute_value=True, status_value="proceed", recommended_action_value="",
            blocking_reason_value="", requested_user_input_value=[])

    def load_from(self, response: Response) -> None:
        """Takes every structured field of a phase response (the triage phase starts the state this way)."""
        self.intent = response.intent
        self.user_goal = response.user_goal
        self.mcp_routing = response.mcp_routing
        self.task_category = response.task_category
        self.actions = response.actions
        self.missing_information = response.missing_information
        self.constraints = response.constraints
        self.safety_and_validation = response.safety_and_validation
        self.next_step = response.next_step

    def needs_user_input(self) -> bool:
        """
        True when next_step signals the flow must pause for the user.
        next_step is the authoritative control-flow object (see prompts/advanced/0_generic_prompt.txt).
        """
        if not self.next_step:
            return False

        status = self.next_step.status
        if status and status.get_value() in ("awaiting_user_input", "awaiting_confirmation"):
            return True

        return False

    def needs_confirmation(self) -> bool:
        """True when the flow waits for a yes or a no (next_step.status is awaiting_confirmation)."""
        return bool(self.next_step and self.next_step.status
                    and self.next_step.status.get_value() == "awaiting_confirmation")

    def next_step_says_retry(self) -> bool:
        """True when next_step.status is "retry" or "error": the phase asks to be run again."""
        return bool(self.next_step and self.next_step.status
                    and self.next_step.status.get_value() in ("retry", "error"))

    def requires_confirmation(self) -> bool:
        return bool(
            self.safety_and_validation
            and self.safety_and_validation.requires_confirmation
            and self.safety_and_validation.requires_confirmation.get_value()
        )

    def final_text(self) -> str:
        """The reply for the user: the expected outcome written by the last phase."""
        if self.user_goal and self.user_goal.expected_outcome:
            return self.user_goal.expected_outcome.get_value()
        return ""
