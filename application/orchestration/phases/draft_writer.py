# Phase 7 - Draft Writer
# Synthesizes all action outputs into a first draft of the user response.

from domain.value_objects.model import GithubModels

from application.orchestration.phase import PhaseSpec
from application.orchestration.schemas import property_schema


def _properties():
    return {"user_goal": property_schema("user_goal")}


def _apply(state, response):
    if response.user_goal:
        state.user_goal = response.user_goal


DRAFT_WRITER = PhaseSpec(
    id=7,
    model=GithubModels.GPT_4_1,
    intent=("decision_support", ("information_request",), 0.9),
    format_name="draft_writer_phase7_response_format",
    required=("user_goal",),
    properties=_properties,
    build_input=lambda state: {
        "user_goal": state.user_goal,
        "task_category": state.task_category,
        "actions": state.actions,
        "constraints": state.constraints,
    },
    apply=_apply,
)
