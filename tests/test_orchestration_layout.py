"""
The layout of application/ says what each folder is for, and the dependencies go one way. The runtime is the path of a message,
top to bottom: profile -> flow -> step -> state, and `support` is the base under all of it.

    runtime/profile   runs one profile (its token, its inputs, its flow)           uses flow, step, state, support (never assembly)
    runtime/flow      runs the steps of one flow, its pauses and resumes           uses step, state, support (never a profile)
    runtime/step      runs one step: its spec, its runner, the registry, library/  uses state, support (never a flow or a profile)
    runtime/state     the data a run carries                                      uses support
    support           helpers with no business rules                              uses nothing of the runtime (metrics and model selection are in runtime/step)
    assembly          start-up only: reads the JSON files, refuses what cannot work; it uses the runtime (it builds the Agent
                      defined in runtime/profile/assembled.py) and the runtime never imports it

A flow is a file (flows/<name>.json) and its steps are declarations (step_defs/<name>.json) or code in runtime/step/library/<group>/;
the runtime never has to know a particular one. These tests keep it so.
"""
import ast
import os

import pytest

APPLICATION = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "application")
PREFIX = "application."


def _imports(folder: str):
    """(file, imported module) for every `application...` import under the folder, subfolders included."""
    found = []
    for base, _dirs, files in os.walk(os.path.join(APPLICATION, *folder.split("/"))):
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
        (file, module) for file, module in _imports(layer)
        if module.startswith(forbidden) and not module.startswith(allowed)
    ]


class TestLayout:
    def test_the_old_folders_are_gone(self):
        for old in ("orchestration", "engine", "steps"):
            assert not os.path.exists(os.path.join(APPLICATION, old)), old

    def test_there_are_no_loose_files_in_application_or_runtime(self):
        for folder in (APPLICATION, os.path.join(APPLICATION, "runtime")):
            loose = [n for n in os.listdir(folder) if n.endswith(".py") and n != "__init__.py"]
            assert loose == [], folder

    @pytest.mark.parametrize("layer", ["runtime", "support", "assembly"])
    def test_nothing_imports_a_flow_file(self, layer):
        # a flow is a JSON file; there is no Python package of flows any more (T-05.12)
        assert _offenders(layer, ("flows",)) == []

    def test_the_profile_uses_the_flows_and_steps_and_never_assembly(self):
        assert _offenders("runtime/profile", ("assembly",)) == []

    def test_a_flow_never_uses_a_profile_or_assembly(self):
        assert _offenders("runtime/flow", ("runtime.profile", "assembly")) == []

    def test_a_step_never_uses_a_flow_a_profile_or_assembly(self):
        assert _offenders("runtime/step", ("runtime.flow", "runtime.profile", "assembly")) == []

    def test_the_step_library_uses_only_the_state_the_support_and_the_shape_of_a_step(self):
        # the steps that are code: the spec, the registry, the state, the support; never the runner or anything above it
        assert _offenders("runtime/step/library", ("runtime.flow", "runtime.profile", "assembly", "runtime.step.runner")) == []

    def test_the_shared_machinery_uses_no_step_of_one_particular_flow(self):
        # the runtime reaches the steps through the registry; only the shared steps (common/) are named
        particular = ("runtime.step.library.special", "runtime.step.library.movement", "runtime.step.library.expression")
        for layer in ("runtime/profile", "runtime/flow", "runtime/state", "support", "assembly"):
            assert _offenders(layer, particular) == [], layer
        for module in ("runner", "spec", "build", "declared", "functions", "registry", "catalog"):
            path = os.path.join(APPLICATION, "runtime", "step", f"{module}.py")
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            names = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
            assert [m for m in names if m.startswith(tuple(PREFIX + p for p in particular))] == [], module

    def test_state_uses_only_the_support(self):
        assert _offenders("runtime/state", ("runtime.profile", "runtime.flow", "runtime.step", "assembly")) == []

    def test_support_uses_nothing_of_the_runtime_or_assembly(self):
        assert _offenders("support", ("assembly", "runtime")) == []

    def test_the_runtime_and_support_never_read_assembly(self):
        for layer in ("runtime", "support"):
            assert _offenders(layer, ("assembly",)) == [], layer
