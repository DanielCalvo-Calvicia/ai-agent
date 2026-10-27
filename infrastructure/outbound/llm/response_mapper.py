# ===============================================
#  RESPONSE MAPPER
#  Turns what the LLM answered (text or a JSON object) into
#  a domain Response. One small function per section.
# ===============================================

from typing import Any, Dict, List, Optional

from domain.entities.llm_response.action import Action, create_action
from shared_logging import get_logger
from domain.entities.llm_response.response import Response
from domain.entities.llm_response.tokens_usage import TokensUsage, create_tokens_usage
from domain.value_objects.llm_response.constraints.constraints import Constraints, create_constraints
from domain.value_objects.llm_response.intent.intent import Intent, create_intent
from domain.value_objects.llm_response.mcp_routing.mcp_routing import MCPRouting, create_mcp_routing
from domain.value_objects.llm_response.missing_information.missing_information import MissingInformation, create_missing_information
from domain.value_objects.llm_response.next_step.next_step import NextStep, create_next_step
from domain.value_objects.llm_response.safety_and_validation.safety_and_validation import SafetyAndValidation, create_safety_and_validation
from domain.value_objects.llm_response.task_category.task_category import TaskCategory, create_task_category
from domain.value_objects.llm_response.user_goal.user_goal import UserGoal, create_user_goal

JsonObject = Dict[str, Any]

# Most subactions one action may have (the schema asks for the same limit).
MAX_SUBACTIONS = 10

logger = get_logger(__name__)


def build_response(response_ai: JsonObject | str, tokens_usage: JsonObject) -> Response:
    """
    `response_ai` is the plain text of the answer or its parsed JSON object.
    `tokens_usage` needs prompt_tokens, completion_tokens and total_tokens.
    """
    if isinstance(response_ai, str):
        return Response(
            intent=None, user_goal=None, mcp_routing=None, task_category=None, actions=None,
            tokens_usage=_map_tokens_usage(tokens_usage),
            text=response_ai,
        )

    return Response(
        intent=_map_intent(response_ai),
        user_goal=_map_user_goal(response_ai),
        mcp_routing=_map_mcp_routing(response_ai),
        task_category=_map_task_category(response_ai),
        actions=_map_actions(response_ai),
        missing_information=_map_missing_information(response_ai),
        constraints=_map_constraints(response_ai),
        safety_and_validation=_map_safety_and_validation(response_ai),
        next_step=_map_next_step(response_ai),
        tokens_usage=_map_tokens_usage(tokens_usage),
        text=None,
        raw=response_ai,
    )


# -----------------------------------------------
#  SECTIONS
# -----------------------------------------------

def _map_intent(data: JsonObject) -> Optional[Intent]:
    if "intent" not in data:
        return None
    intent = data["intent"]
    return create_intent(
        primary=intent.get("primary", ""),
        secondary=intent.get("secondary", []),
        confidence=intent.get("confidence", 0.0),
    )


def _map_user_goal(data: JsonObject) -> Optional[UserGoal]:
    if "user_goal" not in data:
        return None
    goal = data["user_goal"]
    return create_user_goal(
        summary_value=goal.get("summary", ""),
        expected_outcome_value=goal.get("expected_outcome", ""),
    )


def _map_mcp_routing(data: JsonObject) -> Optional[MCPRouting]:
    if "mcp_routing" in data and "required_servers" in data["mcp_routing"]:
        return create_mcp_routing(required_servers=data["mcp_routing"]["required_servers"])
    return None


def _map_task_category(data: JsonObject) -> Optional[TaskCategory]:
    if "task_category" not in data:
        return None
    category = data["task_category"]
    return create_task_category(
        domain_value=category.get("domain", ""),
        type_value=category.get("type", ""),
        complexity_value=category.get("complexity", ""),
    )


def _map_actions(data: JsonObject) -> Optional[List[Action]]:
    if "actions" not in data:
        return None
    return [_map_action(action) for action in data["actions"]]


def _map_action(action: JsonObject) -> Action:
    mcp_context = action.get("mcp_context") or {}
    mapped = create_action(
        id_value=action.get("id", ""),
        description_value=action.get("description", ""),
        action_type_value=action.get("action_type", ""),
        mcp_context_server_id=mcp_context.get("server_id", ""),
        mcp_context_tool_name=mcp_context.get("tool_name", ""),
        mcp_context_parameters=mcp_context.get("parameters", {}),
        dependencies_list=action.get("dependencies", []),
        required_inputs_list=action.get("required_inputs", []),
        output_value=action.get("output", ""),
        error_value=action.get("error", ""),
    )

    subactions = action.get("subactions") or []
    if len(subactions) > MAX_SUBACTIONS:
        logger.warning("Too many subactions, keeping the first ones", action_id=mapped.id.get_value(), count=len(subactions))
        subactions = subactions[:MAX_SUBACTIONS]

    if subactions:
        mapped.subactions = {sub.id.get_value(): sub for sub in (_map_action(s) for s in subactions)}

    return mapped


def _map_missing_information(data: JsonObject) -> Optional[List[MissingInformation]]:
    """The schema asks for a list (one entry per missing piece); a single object is accepted as a list of one."""
    info = data.get("missing_information")
    if not info:
        return None
    entries = [info] if isinstance(info, dict) else info
    return [
        create_missing_information(
            field_value=entry["field"],
            why_needed_value=entry["why_needed"],
            blocking_value=entry["blocking"],
        )
        for entry in entries
    ]


def _map_constraints(data: JsonObject) -> Optional[Constraints]:
    constraints = data.get("constraints")
    if constraints is None:
        return None
    return create_constraints(
        format=constraints.get("format", ""),
        language=constraints.get("language", ""),
        tone=constraints.get("tone", ""),
        length=constraints.get("length", "short"),
    )


def _map_safety_and_validation(data: JsonObject) -> Optional[SafetyAndValidation]:
    if "safety_and_validation" not in data:
        return None
    safety = data["safety_and_validation"]
    return create_safety_and_validation(
        sensitive_value=safety.get("sensitive", False),
        requires_confirmation_value=safety.get("requires_confirmation", False),
    )


def _map_next_step(data: JsonObject) -> Optional[NextStep]:
    if "next_step" not in data:
        return None
    step = data["next_step"]
    return create_next_step(
        ready_to_execute_value=step.get("ready_to_execute", False),
        status_value=step.get("status", ""),
        recommended_action_value=step.get("recommended_action", ""),
        blocking_reason_value=step.get("blocking_reason", ""),
        requested_user_input_value=step.get("requested_user_input", []),
        retry_action_id_value=step.get("retry_action_id", ""),
    )


def _map_tokens_usage(tokens_usage: JsonObject) -> TokensUsage:
    return create_tokens_usage(
        prompt_tokens=tokens_usage["prompt_tokens"],
        completion_tokens=tokens_usage["completion_tokens"],
        total_tokens=tokens_usage["total_tokens"],
    )
