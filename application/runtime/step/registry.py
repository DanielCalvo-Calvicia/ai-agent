# ===============================================
#  STEP REGISTRY
#  Every step is defined in one place only. A code step (and the two prompts the engine runs itself, the answer check and the
#  clarification) registers itself from its Python file, with the constants at the top. An LLM step is a JSON declaration
#  (step_defs/<name>.json, T-05.16) and enters here from it. The catalog, the prompt loader, the model selection and the metrics
#  take their tables from here. A new LLM step = its declaration and its prompt; a new code step = its file.
# ===============================================

import importlib
import os
import sys
from dataclasses import dataclass
from types import ModuleType
from typing import Dict, List, Tuple

PACKAGE = "application.steps"
PHASES_DIR = os.path.dirname(os.path.abspath(__file__))

LLM = "llm"                          # one LLM call
LLM_PER_ACTION = "llm_per_action"    # one LLM call for every planned action
CODE = "code"                        # plain code, no model and no prompt
KINDS = (LLM, LLM_PER_ACTION, CODE)

# The folders of the steps, in the order the catalog lists them: the text flows (identification, conversation, special)
# first, in execution order, then the movement flow, then the expression flow.
GROUP_ORDER = {"identification": 0, "common": 0, "special": 0, "movement": 1, "expression": 2}
TEXT_GROUPS = tuple(group for group, rank in GROUP_ORDER.items() if rank == 0)


@dataclass(frozen=True)
class StepEntry:
    name: str           # STEP_NAME: the name config files and metrics use
    kind: str
    legacy_id: int      # PHASE_ID: the old phase number, kept as a label
    group: str          # the folder of the file: identification, common, special, movement, expression
    module: ModuleType


_STEPS: Dict[str, StepEntry] = {}
_loaded = False


def register_step(module_name: str, kind: str) -> StepEntry:
    """
    Called by a step file, right after the constants at its top (`register_step(__name__, "llm")`).
    A name or a legacy id that another file already registered is an error.
    """
    if kind not in KINDS:
        raise ValueError(f"{module_name}: unknown step kind {kind!r}. Kinds: {', '.join(KINDS)}")

    module = sys.modules[module_name]
    if (kind == CODE) == getattr(module, "LLM", True):
        raise ValueError(f"{module_name}: kind {kind!r} does not match LLM = {getattr(module, 'LLM', True)}")

    entry = StepEntry(
        name=module.STEP_NAME,
        kind=kind,
        legacy_id=module.PHASE_ID,
        group=module_name.split(".")[-2],
        module=module,
    )

    for other in _STEPS.values():
        if other.module.__name__ == module_name:
            continue                                    # the same file imported again replaces its entry
        if other.name == entry.name:
            raise ValueError(f"step {entry.name!r} is already registered by {other.module.__name__}")
        if other.legacy_id == entry.legacy_id:
            raise ValueError(f"phase id {entry.legacy_id} is already used by step {other.name!r}")

    _STEPS[entry.name] = entry
    return entry


def load_all() -> None:
    """Imports every step file once, so each one registers itself."""
    global _loaded
    if _loaded:
        return
    for folder in sorted(os.listdir(PHASES_DIR)):
        path = os.path.join(PHASES_DIR, folder)
        if not os.path.isdir(path) or folder.startswith("__"):
            continue
        for name in sorted(os.listdir(path)):
            if name.endswith(".py") and not name.startswith("__"):
                importlib.import_module(f"{PACKAGE}.{folder}.{name[:-3]}")
    _register_declared()
    _loaded = True


def _register_declared() -> None:
    """The LLM steps of step_defs/ of this repository: each one a catalog entry whose constants are its declaration's."""
    from application.steps.declared import declaration_module, repository_declarations
    for name, declaration in repository_declarations().items():
        kind = declaration.get("kind")
        if kind not in (LLM, LLM_PER_ACTION) or name in _STEPS:
            continue                                    # a code step is registered by its own file
        _STEPS[name] = StepEntry(name, kind, declaration["legacy_id"], declaration.get("group", "special"),
                                 declaration_module(name, declaration))


def _order(entry: StepEntry) -> Tuple[int, int]:
    return GROUP_ORDER.get(entry.group, len(GROUP_ORDER)), entry.legacy_id


def all_steps() -> List[StepEntry]:
    """Every registered step, the text flows first and each flow in execution order."""
    load_all()
    return sorted(_STEPS.values(), key=_order)


def steps_of_kind(*kinds: str) -> List[StepEntry]:
    return [entry for entry in all_steps() if entry.kind in kinds]


def step(name: str) -> StepEntry:
    load_all()
    if name not in _STEPS:
        raise KeyError(f"unknown step: {name!r}. Steps: {', '.join(e.name for e in all_steps())}")
    return _STEPS[name]
