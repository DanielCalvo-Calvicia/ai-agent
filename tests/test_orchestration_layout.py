"""
The layout of application/ says what each folder is for, and the dependencies go one way:

    engine  ->  steps (the shape of a step, the shared steps), state, support        (a flow is a file: flows/<name>.json, T-05.12)
    steps   ->  state, support                                                       (never a flow or the engine)
    engine/state, engine/support -> nothing of the above (support only reads the step catalog)

`state` and `support` are the base and live inside engine/ (application/engine/state, application/engine/support).
These tests keep it so. A new flow is a file in flows/ and its steps are in steps/<group>/; the engine never has to know it.
"""
import ast
import os

import pytest

APPLICATION = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "application")
PREFIX = "application."

# folder (below application/) -> whether its subfolders belong to it. The engine's own files are the ones
# directly in engine/; state/ and support/ below it are their own layers.
LAYERS = {
    "engine": False,
    "engine/state": True,
    "engine/support": True,
    "steps": True,
    "flows": True,
}


def _imports(folder: str, recursive: bool):
    """(file, imported module) for every `application...` import under the folder."""
    found = []
    base_dir = os.path.join(APPLICATION, *folder.split("/"))
    for base, dirs, files in os.walk(base_dir):
        if not recursive:
            dirs[:] = []
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(PREFIX):
                    found.append((os.path.relpath(path, APPLICATION), node.module[len(PREFIX):]))
    return found


def _offenders(layer: str, forbidden: tuple, allowed: tuple = ()):
    return [
        (file, module) for file, module in _imports(layer, LAYERS[layer])
        if module.startswith(forbidden) and not module.startswith(allowed)
    ]


class TestLayout:
    def test_the_old_orchestration_folder_is_gone(self):
        assert not os.path.exists(os.path.join(APPLICATION, "orchestration"))

    def test_there_are_no_loose_files_in_application(self):
        loose = [n for n in os.listdir(APPLICATION) if n.endswith(".py") and n != "__init__.py"]
        assert loose == []

    @pytest.mark.parametrize("layer", ["engine", "engine/state", "engine/support", "steps"])
    def test_nothing_below_the_flows_imports_a_flow(self, layer):
        assert _offenders(layer, ("flows",)) == []

    def test_the_engine_uses_only_the_shared_steps(self):
        # steps.phase (the shape of a step), steps.registry, steps.catalog and steps.common (answer checker,
        # clarification, and the writer and editor the conversation and special flows share); never the steps of
        # one particular flow
        assert _offenders("engine", ("steps.identification", "steps.special", "steps.movement", "steps.expression")) == []

    def test_state_depends_on_nothing_else_of_the_application(self):
        assert _offenders("engine/state", ("steps", "flows", "engine.support", "engine.pipeline", "engine.flow",
                                           "engine.phase_runner", "engine.answer_check", "engine.clarification")) == []

    def test_support_only_reads_the_step_catalog(self):
        # metrics and model selection take their tables from it; nothing else of steps, nothing of the engine
        assert _offenders("engine/support", ("engine.pipeline", "engine.flow", "engine.phase_runner",
                                             "engine.answer_check", "engine.clarification", "engine.state")) == []
        assert _offenders("engine/support", ("steps",), allowed=("steps.catalog",)) == []

    def test_steps_do_not_use_the_engine(self):
        # only its base: state and support
        assert _offenders("steps", ("engine",), allowed=("engine.state", "engine.support")) == []
