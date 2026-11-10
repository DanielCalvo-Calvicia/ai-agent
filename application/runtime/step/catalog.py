# ===============================================
#  PHASE CATALOG
#  Every phase of every flow, read from the step registry (each step file registers itself, runtime/step/registry.py).
#  The prompt loader, the model selection and the metrics take their tables from here,
#  so a phase is defined in one place only. A new phase = its file.
# ===============================================

from dataclasses import dataclass
from types import ModuleType
from typing import Dict, Optional

from application.runtime.step.registry import CODE, TEXT_GROUPS, all_steps
from domain.value_objects.llm_request.model import GoogleModels


@dataclass(frozen=True)
class PhaseInfo:
    id: int
    step_name: str
    default_model: GoogleModels
    prompt_file: Optional[str]      # None for a phase whose prompt is a constant in its file


def _info(module: ModuleType) -> PhaseInfo:
    return PhaseInfo(
        id=module.PHASE_ID,
        step_name=module.STEP_NAME,
        default_model=module.DEFAULT_MODEL,
        prompt_file=getattr(module, "PROMPT_FILE", None),
    )


# The phases that are one LLM call (or one per action). The text ones (identification, conversation and special flows)
# come first, in execution order: that order is the order of the steps in the tables of docs/models.
PHASES: Dict[int, PhaseInfo] = {
    entry.legacy_id: _info(entry.module) for entry in all_steps() if entry.kind != CODE
}

# The same for the text flows only (everything but movement and expression). The cost, budget and ratings tables cover exactly these steps.
CONVERSATION_PHASES: Dict[int, PhaseInfo] = {
    entry.legacy_id: _info(entry.module) for entry in all_steps() if entry.kind != CODE and entry.group in TEXT_GROUPS
}
