# Phase 4 - Cognitive Worker
# Does the work of one action that needs no tool (analysis, writing, a robot request...). One LLM call per action.

from typing import Dict

from domain.value_objects.llm_request.model import GithubModels

from application.orchestration.support.action_tree import with_outputs
from application.orchestration.state.flow_state import FlowState
from application.orchestration.phases.phase import ActionPhaseSpec
from application.orchestration.support.schemas import ACTIONS_SCHEMA_FILE

# --- What this phase uses ---------------------------------------------------
PHASE_ID = 4
STEP_NAME = "cognitive_worker"
MODEL_ENV_VAR = "AI_AGENT_MODEL_PHASE_4"
DEFAULT_MODEL = GithubModels.GPT_4_1
PROMPT_FILE = "prompts/4_cognitive_worker.txt"
FORMAT_NAME = "phase4_single_action_response_format"
INTENT = ("decision_support", (), 0.9)
ACTIONS_SCHEMA = ACTIONS_SCHEMA_FILE
# -----------------------------------------------------------------------------

COGNITIVE_WORKER = ActionPhaseSpec(
    id=PHASE_ID,
    step_name=STEP_NAME,
    prompt_file=PROMPT_FILE,
    model=DEFAULT_MODEL,
    intent=INTENT,
    format_name=FORMAT_NAME,
    schema_file=ACTIONS_SCHEMA,
)


def build_extra(state: FlowState, dependency_outputs: Dict[str, str], subaction_outputs: Dict[str, str]) -> dict:
    """What the worker is told besides the action: the goal and the results of the actions it needs."""
    return with_outputs({"user_goal": state.user_goal}, dependency_outputs, subaction_outputs)
