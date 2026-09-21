# ===============================================
#  PHASE DEFINITIONS
#  A phase is data (which model, which schema) plus two small
#  functions: what it reads from the state and what it writes back.
# ===============================================

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from application.orchestration.flow_state import FlowState
from domain.entities.response import Response
from domain.value_objects.model import GithubModels

# Values a phase feeds to the LLM as its user message. A str is sent as is,
# a dict is sent as str(dict) (the format the prompts were written against).
PhaseInput = Any


@dataclass(frozen=True)
class PhaseSpec:
    """One LLM call that answers with the phase's whole response schema."""
    id: int
    model: GithubModels
    intent: Tuple[str, Tuple[str, ...], float]   # primary, secondary, confidence
    format_name: str
    required: Tuple[str, ...]
    properties: Callable[[], Dict[str, Any]]     # loads the JSON schema pieces lazily
    build_input: Callable[[FlowState], PhaseInput]
    apply: Callable[[FlowState, Response], None]


@dataclass(frozen=True)
class Step:
    """
    One position of the pipeline. `run` does the phase work on the shared state.
    `pause_if` is checked afterwards: when true the flow stops and the user is asked.
    """
    name: str
    run: Callable[[FlowState], None]
    pause_if: Optional[Callable[[FlowState], bool]] = None
    # For steps that write next_step: run again while it says "retry" or "error".
    phase_id: Optional[int] = None
    retry_on_status: bool = False
