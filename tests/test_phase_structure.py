# The phase files are the one place that says what a phase uses. These tests keep them that way:
# one phase per file, every constant present, every file they point at really there.

import ast
import importlib
import os

import pytest

from application.orchestration.phases import catalog as phase_catalog
from application.orchestration.support.schemas import SCHEMAS_ROOT
from application.system_prompts.general import CAPABILITIES_FILE, GENERIC_PROMPT_FILE, PROJECT_ROOT

PHASES_DIR = os.path.join(PROJECT_ROOT, "application", "orchestration", "phases")
REQUIRED_CONSTANTS = ("PHASE_ID", "STEP_NAME", "MODEL_ENV_VAR", "DEFAULT_MODEL")
NAME_CONSTANTS = ("PHASE_ID", "STEP_NAME")      # a step that runs no LLM (LLM = False) has only these


def _phase_files():
    found = []
    for folder in sorted(os.listdir(PHASES_DIR)):
        path = os.path.join(PHASES_DIR, folder)
        if os.path.isdir(path) and not folder.startswith("__"):
            for name in sorted(os.listdir(path)):
                if name.endswith(".py") and not name.startswith("__"):
                    found.append((folder, name[:-3]))
    return found


PHASE_FILES = _phase_files()


def _module(folder: str, name: str):
    return importlib.import_module(f"application.orchestration.phases.{folder}.{name}")


def _top_level_assignments(folder: str, name: str, constant: str) -> int:
    with open(os.path.join(PHASES_DIR, folder, f"{name}.py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    return sum(
        1 for node in tree.body
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == constant for t in node.targets)
    )


@pytest.mark.parametrize("folder,name", PHASE_FILES)
class TestEachPhaseFile:
    def test_it_defines_exactly_one_phase(self, folder, name):
        assert _top_level_assignments(folder, name, "PHASE_ID") == 1

    def test_it_declares_what_it_uses(self, folder, name):
        module = _module(folder, name)
        required = REQUIRED_CONSTANTS if getattr(module, "LLM", True) else NAME_CONSTANTS
        for constant in required:
            assert hasattr(module, constant), f"{folder}/{name}.py has no {constant}"
        if getattr(module, "LLM", True):
            assert module.MODEL_ENV_VAR == f"AI_AGENT_MODEL_PHASE_{module.PHASE_ID}"

    def test_its_prompt_file_exists(self, folder, name):
        prompt = getattr(_module(folder, name), "PROMPT_FILE", None)
        if prompt is not None:
            assert os.path.isfile(os.path.join(PROJECT_ROOT, prompt)), prompt

    def test_its_schema_files_exist(self, folder, name):
        module = _module(folder, name)
        files = [ref.file for ref in getattr(module, "SCHEMAS", {}).values()]
        files += [getattr(module, "ACTIONS_SCHEMA")] if hasattr(module, "ACTIONS_SCHEMA") else []
        for file in files:
            assert os.path.isfile(os.path.join(SCHEMAS_ROOT, file)), file

    def test_it_is_in_the_catalog(self, folder, name):
        module = _module(folder, name)
        assert module in phase_catalog.PHASE_MODULES + phase_catalog.NON_LLM_MODULES

    def test_an_llm_phase_is_not_listed_as_a_non_llm_step(self, folder, name):
        module = _module(folder, name)
        assert (module in phase_catalog.NON_LLM_MODULES) == (not getattr(module, "LLM", True))


class TestCatalog:
    ALL = phase_catalog.PHASE_MODULES + phase_catalog.NON_LLM_MODULES

    def test_phase_ids_and_step_names_are_unique(self):
        ids = [m.PHASE_ID for m in self.ALL]
        names = [m.STEP_NAME for m in self.ALL]
        assert len(ids) == len(set(ids))
        assert len(names) == len(set(names))

    def test_the_catalog_lists_every_phase_file(self):
        assert len(self.ALL) == len(PHASE_FILES)

    def test_conversation_flow_keeps_its_own_table_for_the_cost_tools(self):
        from application.orchestration.support.metrics import ALL_PHASE_NAMES, PHASE_NAMES
        assert set(PHASE_NAMES) < set(ALL_PHASE_NAMES)
        assert "motion_planner" in ALL_PHASE_NAMES.values() and "motion_planner" not in PHASE_NAMES.values()

    def test_the_shared_prompt_files_exist(self):
        assert os.path.isfile(os.path.join(PROJECT_ROOT, GENERIC_PROMPT_FILE))
        assert os.path.isfile(os.path.join(PROJECT_ROOT, CAPABILITIES_FILE))
