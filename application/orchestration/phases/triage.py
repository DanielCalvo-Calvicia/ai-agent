# Phase 1 - Triage Specialist
# Classifies intent, extracts user goal and task category.

from domain.value_objects.model import GithubModels

from application.orchestration.phase import PhaseSpec
from application.orchestration.schemas import property_schema


def _properties():
    return {
        "intent": property_schema("intent"),
        "user_goal": property_schema("user_goal"),
        "task_category": property_schema("task_category"),
        "next_step": property_schema("next_step"),
    }


TRIAGE = PhaseSpec(
    id=1,
    model=GithubModels.GPT_4_1_MINI,
    intent=("clarification_request", ("information_request",), 1.0),
    format_name="triage_specialist_phase1_response_format",
    required=("intent", "user_goal", "task_category", "next_step"),
    properties=_properties,
    build_input=lambda state: state.message_with_history(),
    # The triage answer starts the state: every field it carries is taken.
    apply=lambda state, response: state.load_from(response),
)
