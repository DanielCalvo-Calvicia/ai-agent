# ===============================================
#  PHASE CATALOG
#  Every phase of every flow, read from the constants at the top of its own file.
#  The prompt loader, the model selection and the metrics take their tables from here,
#  so a phase is defined in one place only. A new phase = its file + one line below.
# ===============================================

from dataclasses import dataclass
from types import ModuleType
from typing import Dict, Optional, Tuple

from application.orchestration.phases.common import answer_checker, draft_writer, editor_in_chief, user_clarification
from application.orchestration.phases.expression import emotion_reader, gesture_builder
from application.orchestration.phases.identification import triage
from application.orchestration.phases.movement import motion_planner, motion_validator
from application.orchestration.phases.special import (
    cognitive_worker,
    data_engineer,
    mcp_operator,
    project_manager,
    safety_gate,
)
from domain.value_objects.llm_request.model import GithubModels

# The phases that are one LLM call (or one per action). The text ones (identification, conversation and special flows)
# come first, in execution order: that order is the order of the step list in config/step_models.json.
MOVEMENT_FLOW_MODULES: Tuple[ModuleType, ...] = (motion_planner,)
EXPRESSION_FLOW_MODULES: Tuple[ModuleType, ...] = (emotion_reader,)

TEXT_FLOW_MODULES: Tuple[ModuleType, ...] = (
    triage,
    project_manager,
    safety_gate,
    cognitive_worker,
    mcp_operator,
    data_engineer,
    draft_writer,
    editor_in_chief,
    answer_checker,
    user_clarification,
)

PHASE_MODULES: Tuple[ModuleType, ...] = TEXT_FLOW_MODULES + MOVEMENT_FLOW_MODULES + EXPRESSION_FLOW_MODULES

# Steps that run no LLM: no model, no prompt. They have an id and a name for errors and logs.
NON_LLM_MODULES: Tuple[ModuleType, ...] = (motion_validator, gesture_builder)


@dataclass(frozen=True)
class PhaseInfo:
    id: int
    step_name: str
    model_env_var: str
    default_model: GithubModels
    prompt_file: Optional[str]      # None for a phase whose prompt is a constant in its file


def _info(module: ModuleType) -> PhaseInfo:
    return PhaseInfo(
        id=module.PHASE_ID,
        step_name=module.STEP_NAME,
        model_env_var=module.MODEL_ENV_VAR,
        default_model=module.DEFAULT_MODEL,
        prompt_file=getattr(module, "PROMPT_FILE", None),
    )


PHASES: Dict[int, PhaseInfo] = {info.id: info for info in map(_info, PHASE_MODULES)}

# The same for the text flows only (everything but movement). The cost, budget and ratings tables cover exactly these steps.
CONVERSATION_PHASES: Dict[int, PhaseInfo] = {info.id: info for info in map(_info, TEXT_FLOW_MODULES)}
