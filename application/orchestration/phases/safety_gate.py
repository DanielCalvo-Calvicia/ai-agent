# Phase 3 - Safety & Quality Gatekeeper
# Validates actions for safety and decides if user confirmation is needed.

from domain.value_objects.model import GithubModels

from application.orchestration.phase import PhaseSpec
from application.orchestration.schemas import property_schema


def _properties():
    return {
        "safety_and_validation": property_schema("safety_and_validation"),
        "next_step": property_schema("next_step"),
    }


def _apply(state, response):
    state.safety_and_validation = response.safety_and_validation
    state.next_step = response.next_step


def _build_input(state) -> dict:
    user_message = {
        "actions": state.actions,
        "next_step": state.next_step,
    }
    if state.answers:
        user_message["user_answers"] = state.answers_as_dicts()
    return user_message


SAFETY_GATE = PhaseSpec(
    id=3,
    model=GithubModels.GPT_4_1,
    intent=("decision_support", ("information_request",), 0.9),
    format_name="safety_quality_gatekeeper_phase3_response_format",
    required=("safety_and_validation", "next_step"),
    properties=_properties,
    build_input=lambda state: _build_input(state),
    apply=_apply,
)
