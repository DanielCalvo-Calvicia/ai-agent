"""MCP config files: ``${NAME}`` references are filled from the environment (no machine-specific path in git)."""

import json

from infrastructure.outbound.mcp.config import expand_env, load_mcp_configs


def test_expand_env_fills_strings_lists_and_dicts(monkeypatch):
    monkeypatch.setenv("MCP_TEST_DIR", "/srv/files")
    value = {"args": ["--mount", "source=${MCP_TEST_DIR},target=/data"], "nested": {"k": "${MCP_TEST_DIR}"}, "n": 3}

    assert expand_env(value) == {
        "args": ["--mount", "source=/srv/files,target=/data"],
        "nested": {"k": "/srv/files"},
        "n": 3,
    }


def test_expand_env_keeps_a_reference_whose_variable_is_not_set(monkeypatch):
    monkeypatch.delenv("MCP_TEST_UNSET", raising=False)

    assert expand_env("source=${MCP_TEST_UNSET}") == "source=${MCP_TEST_UNSET}"


def test_load_mcp_configs_expands_references(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_TEST_DIR", "/srv/files")
    (tmp_path / "files.json").write_text(
        json.dumps({"files": {"type": "stdio", "args": ["source=${MCP_TEST_DIR}"]}}), encoding="utf-8"
    )

    [server] = load_mcp_configs(str(tmp_path))

    assert server["config"]["args"] == ["source=/srv/files"]


def test_shipped_filesystem_config_has_no_hardcoded_windows_path():
    [server] = [s for s in load_mcp_configs() if s["name"] == "filesystem"]

    assert not any(":/" in arg or ":\\" in arg for arg in server["config"]["args"] if arg.startswith("type=bind"))
