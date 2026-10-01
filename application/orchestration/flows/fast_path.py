# ===============================================
#  FAST PATH
#  For a plain reply that needs no plan and no action, phases 2 (project manager),
#  3 (safety gate) and 4-6 (action execution) are pure overhead: nothing is being
#  planned, validated or executed, only text written back. Skipping them cuts a
#  simple "hello" from 5 sequential LLM calls down to 3.
#
#  Never applies to anything the project manager would need to plan (a robot_action,
#  an MCP tool call, a multi-step task, or even "explain honestly that this can't be
#  done" - the project manager plans that as a generation action too): project manager
#  is the only phase that plans actions, so any of those must go through the full
#  pipeline. task_category.type == "generation" alone is NOT a safe signal for that:
#  the project manager's own prompt uses "generation" for genuinely multi-step writing
#  tasks too (e.g. "make a table of my family"), which still needs a plan. This is
#  intersected with intent.primary to only fire for a request triage itself is already
#  classifying as pure information/conversation, not a task to carry out.
#
#  Neither field is schema-enforced (intent.primary is free text; task_category.type is
#  an enum but triage/project manager visibly overload "generation"), so this is a
#  heuristic, not a guarantee. It is deliberately conservative: false negatives (missing
#  a chance to skip ahead) are harmless, false positives (skipping a plan that was
#  actually needed) are not, so it only fires when both signals agree.
# ===============================================

import os

from application.orchestration.state.flow_state import FlowState

# task_category.type values (domain/value_objects/task_category/type.py) that can mean
# "just answer", though "generation" alone also covers real multi-step writing tasks.
_SIMPLE_TYPES = {"generation"}
_SIMPLE_COMPLEXITY = "low"
# intent.primary values (free text; not schema-enforced) that, in every prompt example and
# golden scenario in this repo, mean "answer from the conversation", never "carry out a task".
_SIMPLE_INTENTS = {"information_request", "clarification_request"}

ENABLED_VARIABLE = "AI_AGENT_FAST_PATH_ENABLED"


def enabled() -> bool:
    return os.environ.get(ENABLED_VARIABLE, "1") != "0"


def applies(state: FlowState) -> bool:
    if not enabled():
        return False
    if state.needs_user_input():
        return False
    if not state.task_category or not state.intent:
        return False

    complexity = state.task_category.complexity
    task_type = state.task_category.type
    if not complexity or complexity.get_value() != _SIMPLE_COMPLEXITY:
        return False
    if not task_type or task_type.get_value() not in _SIMPLE_TYPES:
        return False
    if state.intent.primary not in _SIMPLE_INTENTS:
        return False

    return True
