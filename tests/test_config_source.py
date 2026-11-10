# The configuration is read once, at start, through a port. These tests cover the file source, the checks every source gets
# (schema_version, name) and that a file that cannot be used is reported by name without stopping the others.

import ast
import json
import os

import pytest

from application.engine.config_snapshot import KINDS, SUPPORTED_SCHEMA_VERSIONS, build_snapshot
from application.outbound.ports.config_ports import ConfigError, ConfigSourcePort, Loaded
from infrastructure.outbound.config.file_source import FileConfigSource

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def write(root, relative, content):
    path = os.path.join(str(root), *relative.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content if isinstance(content, str) else json.dumps(content))


class FakeSource(ConfigSourcePort):
    """A source that is not files: the same data from dictionaries."""

    def __init__(self, data, prompts=None):
        self.data, self.prompts = data, prompts or {}

    def _loaded(self, kind):
        return Loaded(items=dict(self.data.get(kind, {})))

    def load_profiles(self): return self._loaded("profiles")
    def load_flows(self): return self._loaded("flows")
    def load_step_defs(self): return self._loaded("step_defs")
    def load_model_sets(self): return self._loaded("model_sets")
    def load_state_fields(self): return self._loaded("state_fields")
    def load_prompt(self, name): return self.prompts[name]


class TestFileSource:
    def test_empty_folders_give_an_empty_snapshot(self, tmp_path):
        snapshot = build_snapshot(FileConfigSource(str(tmp_path)))
        assert (snapshot.profiles, snapshot.flows, snapshot.step_defs, snapshot.model_sets) == ({}, {}, {}, {})
        assert snapshot.errors == {}

    def test_the_folders_of_the_repository_are_readable_and_hold_no_error(self):
        snapshot = build_snapshot(FileConfigSource(PROJECT_ROOT))
        assert snapshot.errors == {}

    def test_it_reads_every_kind_of_file_by_name(self, tmp_path):
        for kind in KINDS:
            write(tmp_path, f"{kind}/one.json", {"schema_version": 1, "name": "one", "about": kind})
        snapshot = build_snapshot(FileConfigSource(str(tmp_path)))
        assert snapshot.profiles["one"]["about"] == "profiles"
        assert snapshot.flows["one"]["about"] == "flows"
        assert snapshot.step_defs["one"]["about"] == "step_defs"
        assert snapshot.model_sets["one"]["about"] == "model_sets"

    def test_a_file_or_folder_that_starts_with_an_underscore_is_not_loaded(self, tmp_path):
        write(tmp_path, "profiles/good.json", {"schema_version": 1})
        write(tmp_path, "profiles/_template.json", {"schema_version": 1})
        write(tmp_path, "profiles/_unverified/old.json", {"schema_version": 1})
        write(tmp_path, "profiles/README.md", "# not json")
        snapshot = build_snapshot(FileConfigSource(str(tmp_path)))
        assert list(snapshot.profiles) == ["good"]
        assert snapshot.errors == {}

    def test_invalid_json_names_the_file_and_the_line(self, tmp_path):
        write(tmp_path, "profiles/bad.json", '{\n  "schema_version": 1,\n  oops\n}')
        write(tmp_path, "profiles/good.json", {"schema_version": 1})
        snapshot = build_snapshot(FileConfigSource(str(tmp_path)))
        message = snapshot.errors["profiles/bad"]
        assert "bad.json" in message and "line 3" in message
        assert "good" in snapshot.profiles                 # the others are still loaded

    def test_a_file_that_is_not_an_object_is_refused(self, tmp_path):
        write(tmp_path, "flows/list.json", "[1, 2]")
        assert "must hold a JSON object" in build_snapshot(FileConfigSource(str(tmp_path))).errors["flows/list"]

    def test_the_name_inside_a_file_must_be_the_name_of_the_file(self, tmp_path):
        write(tmp_path, "profiles/chat.json", {"schema_version": 1, "name": "other"})
        assert "'other'" in build_snapshot(FileConfigSource(str(tmp_path))).errors["profiles/chat"]


class TestSchemaVersion:
    @pytest.mark.parametrize("data", [{}, {"schema_version": "1"}, {"schema_version": True}, {"schema_version": 1.0}])
    def test_a_missing_or_wrong_type_of_version_is_refused(self, tmp_path, data):
        write(tmp_path, "profiles/p.json", data)
        assert "no integer schema_version" in build_snapshot(FileConfigSource(str(tmp_path))).errors["profiles/p"]

    def test_an_unknown_version_is_refused_and_says_which_are_supported(self, tmp_path):
        write(tmp_path, "step_defs/s.json", {"schema_version": 99})
        message = build_snapshot(FileConfigSource(str(tmp_path))).errors["step_defs/s"]
        assert "schema_version 99" in message and str(SUPPORTED_SCHEMA_VERSIONS[0]) in message

    def test_strict_mode_stops_on_the_first_error(self, tmp_path):
        write(tmp_path, "profiles/p.json", {"schema_version": 99})
        with pytest.raises(ConfigError, match="schema_version 99"):
            build_snapshot(FileConfigSource(str(tmp_path))).raise_on_errors()

    def test_strict_mode_is_silent_when_every_file_is_good(self, tmp_path):
        write(tmp_path, "profiles/p.json", {"schema_version": 1})
        build_snapshot(FileConfigSource(str(tmp_path))).raise_on_errors()


class TestPrompts:
    def test_a_prompt_is_read_once(self, tmp_path):
        write(tmp_path, "prompts/a.txt", "hello")
        snapshot = build_snapshot(FileConfigSource(str(tmp_path)))
        assert snapshot.prompt("prompts/a.txt") == "hello"
        write(tmp_path, "prompts/a.txt", "changed")
        assert snapshot.prompt("prompts/a.txt") == "hello"           # the snapshot does not read it again

    def test_a_missing_prompt_names_it(self, tmp_path):
        with pytest.raises(ConfigError, match="prompts/none.txt"):
            build_snapshot(FileConfigSource(str(tmp_path))).prompt("prompts/none.txt")

    @pytest.mark.parametrize("name", ["../outside.txt", "prompts/../../outside.txt", os.path.abspath(os.sep + "etc")])
    def test_a_name_cannot_leave_the_project(self, tmp_path, name):
        with pytest.raises(ConfigError, match="inside the project"):
            FileConfigSource(str(tmp_path)).load_prompt(name)


class TestAnotherSource:
    def test_a_source_that_is_not_files_gives_the_same_snapshot(self, tmp_path):
        data = {"profiles": {"p": {"schema_version": 1, "flow": "f"}}, "flows": {"f": {"schema_version": 1}}}
        for kind, items in data.items():
            for name, content in items.items():
                write(tmp_path, f"{kind}/{name}.json", content)

        from_files = build_snapshot(FileConfigSource(str(tmp_path)))
        from_fake = build_snapshot(FakeSource(data, {"prompts/a.txt": "text"}))
        assert from_fake.profiles == from_files.profiles and from_fake.flows == from_files.flows
        assert from_fake.errors == from_files.errors == {}
        assert from_fake.prompt("prompts/a.txt") == "text"

    def test_the_checks_are_the_same_for_any_source(self):
        snapshot = build_snapshot(FakeSource({"profiles": {"p": {"schema_version": 2}}}))
        assert "schema_version 2" in snapshot.errors["profiles/p"]


class TestLayering:
    @pytest.mark.parametrize("path", ["application/outbound/ports/config_ports.py", "application/engine/config_snapshot.py"])
    def test_the_application_does_not_import_the_infrastructure(self, path):
        with open(os.path.join(PROJECT_ROOT, *path.split("/")), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        imported = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
        assert not [m for m in imported if m.startswith("infrastructure")]
