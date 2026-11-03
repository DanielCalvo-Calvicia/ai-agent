# The phase files are the one place that says what a phase uses. These tests keep them that way:
# one phase per file, every constant present, every file they point at really there.

import ast
import importlib
import os
import sys
import types

import pytest

from application.steps import registry as step_registry
from application.engine.support.schemas import SCHEMAS_ROOT
from application.system_prompts.general import CAPABILITIES_FILE, GENERIC_PROMPT_FILE, PROJECT_ROOT

PHASES_DIR = os.path.join(PROJECT_ROOT, "application", "steps")
REQUIRED_CONSTANTS = ("PHASE_ID", "STEP_NAME", "DEFAULT_MODEL")
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
    return importlib.import_module(f"application.steps.{folder}.{name}")


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
        assert not hasattr(module, "MODEL_ENV_VAR")       # no environment variable chooses a model any more (T-05.5)

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

    def test_it_is_in_the_registry(self, folder, name):
        module = _module(folder, name)
        assert module in [entry.module for entry in step_registry.all_steps()]

    def test_an_llm_phase_is_not_registered_as_a_code_step(self, folder, name):
        module = _module(folder, name)
        entry = next(e for e in step_registry.all_steps() if e.module is module)
        assert (entry.kind == step_registry.CODE) == (not getattr(module, "LLM", True))


class TestCatalog:
    ALL = step_registry.all_steps()

    def test_phase_ids_and_step_names_are_unique(self):
        ids = [e.legacy_id for e in self.ALL]
        names = [e.name for e in self.ALL]
        assert len(ids) == len(set(ids))
        assert len(names) == len(set(names))

    def test_the_registry_lists_every_phase_file(self):
        assert len(self.ALL) == len(PHASE_FILES)

    def test_the_order_is_the_text_flows_first_then_movement_then_expression(self):
        assert [e.legacy_id for e in self.ALL] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 40, 99, 20, 21, 30, 31]

    def test_the_kinds_are_the_ones_of_the_design(self):
        kinds = {e.name: e.kind for e in self.ALL}
        assert {name for name, kind in kinds.items() if kind == step_registry.LLM_PER_ACTION} == {
            "cognitive_worker", "mcp_operator", "data_engineer"}
        assert {name for name, kind in kinds.items() if kind == step_registry.CODE} == {
            "motion_validator", "gesture_builder", "action_executor"}

    def test_conversation_flow_keeps_its_own_table_for_the_cost_tools(self):
        from application.engine.support.metrics import ALL_PHASE_NAMES, PHASE_NAMES
        assert set(PHASE_NAMES) < set(ALL_PHASE_NAMES)
        assert "motion_planner" in ALL_PHASE_NAMES.values() and "motion_planner" not in PHASE_NAMES.values()

    def test_the_shared_prompt_files_exist(self):
        assert os.path.isfile(os.path.join(PROJECT_ROOT, GENERIC_PROMPT_FILE))
        assert os.path.isfile(os.path.join(PROJECT_ROOT, CAPABILITIES_FILE))


class TestRegisterStep:
    """The registry refuses a step that another file already registered."""

    @pytest.fixture
    def fake(self, monkeypatch):
        monkeypatch.setattr(step_registry, "_STEPS", dict(step_registry._STEPS))

        def make(module_name, step_name, phase_id, llm=True):
            module = types.ModuleType(module_name)
            module.STEP_NAME, module.PHASE_ID = step_name, phase_id
            if not llm:
                module.LLM = False
            monkeypatch.setitem(sys.modules, module_name, module)
            return module_name

        return make

    def test_a_name_registered_twice_fails(self, fake):
        with pytest.raises(ValueError, match="already registered"):
            step_registry.register_step(fake("application.steps.special.copy", "draft_writer", 700), "llm")

    def test_a_phase_id_used_twice_fails(self, fake):
        with pytest.raises(ValueError, match="phase id 7 is already used"):
            step_registry.register_step(fake("application.steps.special.copy", "another_step", 7), "llm")

    def test_an_unknown_kind_fails(self, fake):
        with pytest.raises(ValueError, match="unknown step kind"):
            step_registry.register_step(fake("application.steps.special.copy", "another_step", 701), "other")

    def test_a_kind_that_does_not_match_the_llm_flag_fails(self, fake):
        with pytest.raises(ValueError, match="does not match"):
            step_registry.register_step(fake("application.steps.special.copy", "another_step", 702), "code")

    def test_the_same_file_imported_again_replaces_its_entry(self):
        entry = step_registry.step("draft_writer")
        again = step_registry.register_step(entry.module.__name__, entry.kind)
        assert again == entry
