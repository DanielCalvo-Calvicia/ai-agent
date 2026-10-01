"""
The layout of application/orchestration says what each folder is for, and the dependencies go one way:

    flows  ->  engine, phases, state, support
    engine ->  phases (the shape of a phase, the shared phases), state, support      (never a flow)
    phases ->  state, support                                                        (never a flow or the engine)
    state, support -> nothing of the above

These tests keep it so. A new agent goes in flows/ and phases/<agent>/; the engine never has to know it.
"""
import ast
import os

import pytest

ORCHESTRATION = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "application", "orchestration")
PREFIX = "application.orchestration."


def _imports(folder: str):
    """(file, imported module) for every `application.orchestration...` import under the folder."""
    found = []
    for base, _dirs, files in os.walk(os.path.join(ORCHESTRATION, folder)):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(PREFIX):
                    found.append((os.path.relpath(path, ORCHESTRATION), node.module[len(PREFIX):]))
    return found


def _offenders(folder: str, forbidden: tuple, allowed: tuple = ()):
    return [
        (file, module) for file, module in _imports(folder)
        if module.startswith(forbidden) and not module.startswith(allowed)
    ]


class TestLayout:
    def test_there_are_no_loose_files_in_the_orchestration_folder(self):
        loose = [n for n in os.listdir(ORCHESTRATION) if n.endswith(".py") and n != "__init__.py"]
        assert loose == []

    @pytest.mark.parametrize("folder", ["engine", "state", "support", "phases"])
    def test_nothing_below_the_flows_imports_a_flow(self, folder):
        assert _offenders(folder, ("flows",)) == []

    def test_the_engine_uses_only_the_shared_phases(self):
        # phases.phase (the shape of a phase) and phases.common (triage, answer checker, clarification)
        assert _offenders("engine", ("phases.conversation_flow", "phases.motion_flow")) == []

    def test_state_depends_on_nothing_else_of_the_orchestration(self):
        assert _offenders("state", ("engine", "phases", "support")) == []

    def test_support_only_reads_the_phase_catalog(self):
        # metrics and model selection take their tables from it; nothing else of phases, nothing of the engine
        assert _offenders("support", ("engine", "state")) == []
        assert _offenders("support", ("phases",), allowed=("phases.catalog",)) == []

    def test_phases_do_not_use_the_engine(self):
        assert _offenders("phases", ("engine",)) == []
