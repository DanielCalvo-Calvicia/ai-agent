# Phase 8 - Editor in Chief
# Polishes the draft and produces the final response for the user.

from domain.value_objects.model import GithubModels

from application.orchestration.phase import PhaseSpec
from application.orchestration.schemas import property_schema


def _properties():
    return {
        "user_goal": property_schema("user_goal"),
        "next_step": property_schema("next_step"),
    }


def _apply(state, response):
    if response.user_goal:
        state.user_goal = response.user_goal
    if response.next_step:
        state.next_step = response.next_step


EDITOR_IN_CHIEF = PhaseSpec(
    id=8,
    model=GithubModels.GPT_4_1,
    intent=("decision_support", ("information_request",), 0.9),
    format_name="editor_in_chief_phase8_response_format",
    required=("user_goal", "next_step"),
    properties=_properties,
    build_input=lambda state: {
        "user_goal": state.user_goal,
        "constraints": state.constraints,
        "next_step": state.next_step,
    },
    apply=_apply,
)
