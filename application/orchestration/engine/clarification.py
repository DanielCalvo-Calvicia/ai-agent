# ===============================================
#  CLARIFICATION (phase 99)
#  When the flow must pause, turns the missing inputs into a short
#  message for the user.
# ===============================================

from typing import List

from application.orchestration.state.flow_state import FlowState
from application.orchestration.support.model_selection import model_for_phase
from application.orchestration.engine.phase_runner import PhaseRunner
from application.orchestration.phases.common import user_clarification as phase
from domain.entities.payload import Payload
from domain.value_objects.intent.intent import create_intent
from domain.value_objects.max_tokens import create_max_tokens
from domain.value_objects.message import Role, create_message
from domain.value_objects.temperature import create_temperature


class Clarifier:
    def __init__(self, runner: PhaseRunner) -> None:
        self.runner = runner

    def ask(self, state: FlowState) -> str:
        """
        Collects required inputs from next_step.requested_user_input and
        actions[].required_inputs, then asks the LLM to produce a clear,
        user-facing clarification message.
        """
        required_inputs = self.required_inputs(state)

        if not required_inputs:
            return phase.DEFAULT_MESSAGE

        model = model_for_phase(phase.PHASE_ID, phase.DEFAULT_MODEL)

        inputs_text = "\n".join(f"- {item}" for item in required_inputs)
        user_message_str = f"The following information is required from the user:\n{inputs_text}"

        primary, secondary, confidence = phase.INTENT
        payload = Payload(
            intent=create_intent(primary=primary, secondary=list(secondary), confidence=confidence),
            model=model,
            system_prompt=create_message(Role.SYSTEM, phase.SYSTEM_PROMPT),
            message=create_message(Role.USER, user_message_str),
            reasoning=None,
            temperature=create_temperature(phase.TEMPERATURE),
            top_p=None,
            seed=None,
            max_tokens=create_max_tokens(phase.MAX_TOKENS),
            response_format=None,
            tools=[],
            metadata={},
        )

        response = self.runner.send(payload, phase.PHASE_ID, model)

        return response.text or ""

    def required_inputs(self, state: FlowState) -> List[str]:
        """What the user is asked for: the questions of next_step, then what each action needs."""
        required_inputs: List[str] = []

        if (
            state.next_step
            and state.next_step.requested_user_input
            and state.next_step.requested_user_input.get_length() > 0
        ):
            required_inputs.extend(state.next_step.requested_user_input.get_value())

        if state.actions:
            for action in state.actions:
                if action.required_inputs and action.required_inputs.get_length() > 0:
                    required_inputs.extend(action.required_inputs.get_value())

        # Fallback to blocking_reason or recommended_action if nothing was collected
        if not required_inputs and state.next_step:
            if state.next_step.blocking_reason:
                required_inputs = [state.next_step.blocking_reason.get_value()]
            elif state.next_step.recommended_action:
                required_inputs = [state.next_step.recommended_action.get_value()]

        return required_inputs
