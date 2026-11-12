# ===============================================
#  NAMED FUNCTIONS OF THE STEP DECLARATIONS
#  What a step declaration (step_defs/<name>.json) points to when its input or its result is more than a plain dictionary of fields:
#  `functions.input` builds what the model is told, `functions.apply` writes the answer into the state, `functions.extra` is what a
#  step run once per action is told besides the action (Q08-7). A developer writes one here; a declaration cannot invent one, and
#  assemble() refuses a name that is not in the tables at the end. Moved unchanged from the Python step files they replace (T-05.16).
# ===============================================

from typing import Callable, Dict, Optional

from domain.operations.gesture import DEFAULT_EMOTION, DEFAULT_INTENSITY, EMOTIONS, INTENSITIES
from domain.value_objects.movement.movement import Movement

from application.runtime.state.expression_state import as_expression
from application.runtime.state.flow_state import FlowState
from application.runtime.state.motion_state import as_motion
from application.support.tools.action_tree import with_outputs
from application.support.tools.mcp_servers import describe_servers
from application.ports.outbound.mcp_ports import McpToolsPort

MAX_IMPROVISED = 3          # movements the emotion reader may improvise


# -----------------------------------------------
#  INPUTS: (state, mcp_list, mcp_tools) -> what the model is told
# -----------------------------------------------

def message_with_history(state: FlowState, mcp_list: list, mcp_tools: Optional[McpToolsPort]) -> str:
    """The user message with the earlier turns before it and the answers the user gave after it (triage, motion planner)."""
    return state.message_with_history()


def planner_input(state: FlowState, mcp_list: list, mcp_tools: Optional[McpToolsPort]) -> dict:
    user_message = {
        "user_goal": state.user_goal,
        "task_category": state.task_category,
        "available_mcp_servers": describe_servers(mcp_list, mcp_tools),
    }
    if state.history:
        user_message["conversation_history"] = state.history_as_dicts()
    if state.answers:
        user_message["user_answers"] = state.answers_as_dicts()
    return user_message


def selector_input(state: FlowState, mcp_list: list, mcp_tools: Optional[McpToolsPort]) -> dict:
    """What the tool selector of the fast flow is told: the user's words, the goal, and only the READ-ONLY tools of its scope (T-08.4)."""
    user_message = {
        "user_message": state.message,
        "user_goal": state.user_goal,
        "task_category": state.task_category,
        "available_mcp_servers": describe_servers(mcp_list, mcp_tools, read_only_only=True),
    }
    if state.history:
        user_message["conversation_history"] = state.history_as_dicts()
    if state.answers:
        user_message["user_answers"] = state.answers_as_dicts()
    return user_message


def safety_input(state: FlowState, mcp_list: list, mcp_tools: Optional[McpToolsPort]) -> dict:
    user_message = {
        "actions": state.actions,
        "next_step": state.next_step,
    }
    if state.answers:
        user_message["user_answers"] = state.answers_as_dicts()
    return user_message


def exchange_text(state: FlowState, mcp_list: list, mcp_tools: Optional[McpToolsPort]) -> str:
    state = as_expression(state)
    return f"What the user said:\n{state.message}\n\nWhat the robot answers:\n{state.reply}"


# -----------------------------------------------
#  APPLIES: (state, response) -> writes the answer into the state
# -----------------------------------------------

def load_from_response(state: FlowState, response) -> None:
    """The triage answer starts the state: every field it carries is taken."""
    state.load_from(response)


def movement_from(item: dict) -> Movement:
    """One movement as the planner wrote it. A degrees value that is not a number becomes NaN: the validator refuses it."""
    raw_degrees = item.get("degrees")
    try:
        degrees = float(raw_degrees) if raw_degrees is not None else float("nan")
    except (TypeError, ValueError):
        degrees = float("nan")

    return Movement(arm=str(item.get("arm", "")), degrees=degrees, direction=str(item.get("direction", "")))


def motion_plan_result(state: FlowState, response) -> None:
    state = as_motion(state)
    raw = response.raw or {}
    state.motion_requested = bool(raw.get("is_motion_request", False))
    state.movements = [movement_from(item) for item in (raw.get("movements") or []) if isinstance(item, dict)]
    state.spoken_reply = str(raw.get("spoken_reply") or "")
    state.next_step = response.next_step


def emotion_result(state: FlowState, response) -> None:
    state = as_expression(state)
    raw = response.raw or {}

    emotion = str(raw.get("emotion") or "").strip().lower()
    state.emotion = emotion if emotion in EMOTIONS else DEFAULT_EMOTION

    try:
        intensity = int(raw.get("intensity"))
    except (TypeError, ValueError):
        intensity = DEFAULT_INTENSITY
    state.intensity = intensity if intensity in INTENSITIES else DEFAULT_INTENSITY

    items = [item for item in (raw.get("improvised") or []) if isinstance(item, dict)]
    state.improvised = [movement_from(item) for item in items[:MAX_IMPROVISED]]


# -----------------------------------------------
#  EXTRAS: (state, mcp_list, mcp_tools, dependency_outputs, subaction_outputs) -> what a per-action step is told besides the action
# -----------------------------------------------

def worker_extra(state: FlowState, mcp_list: list, mcp_tools: Optional[McpToolsPort],
                 dependency_outputs: Dict[str, str], subaction_outputs: Dict[str, str]) -> dict:
    """What the worker is told besides the action: the goal and the results of the actions it needs."""
    return with_outputs({"user_goal": state.user_goal}, dependency_outputs, subaction_outputs)


def operator_extra(state: FlowState, mcp_list: list, mcp_tools: Optional[McpToolsPort],
                   dependency_outputs: Dict[str, str], subaction_outputs: Dict[str, str]) -> dict:
    """What the operator is told besides the action: the MCP servers, the safety verdict and earlier results."""
    return with_outputs(
        {
            "available_mcp_servers": describe_servers(mcp_list, mcp_tools),
            "safety_and_validation": state.safety_and_validation,
        },
        dependency_outputs,
        subaction_outputs,
    )


INPUTS: Dict[str, Callable] = {
    "message_with_history": message_with_history, "planner_input": planner_input, "safety_input": safety_input, "exchange_text": exchange_text,
    "selector_input": selector_input,
}
APPLIES: Dict[str, Callable] = {
    "load_from_response": load_from_response, "motion_plan_result": motion_plan_result, "emotion_result": emotion_result,
}
EXTRAS: Dict[str, Callable] = {"worker_extra": worker_extra, "operator_extra": operator_extra}
TABLES = {"input": INPUTS, "apply": APPLIES, "extra": EXTRAS}
