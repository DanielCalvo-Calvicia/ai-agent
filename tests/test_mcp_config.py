"""MCP config files: ``${NAME}`` references are filled from the environment (no machine-specific path in git)."""

import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

from infrastructure.outbound.mcp import config as mcp_config, tool_catalog
from infrastructure.outbound.mcp.config import SUPPORTED_TYPES, expand_env, load_mcp_configs, load_supported_mcp_configs
from infrastructure.outbound.mcp.tool_catalog import MCPToolCatalog


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


def test_streamable_http_is_a_supported_type_next_to_sse():
    assert "sse" in SUPPORTED_TYPES and "streamable_http" in SUPPORTED_TYPES


def test_supported_configs_keep_streamable_http_and_ignore_other_types(tmp_path):
    for name, server_type in (("web", "streamable_http"), ("old", "sse"), ("odd", "websocket"), ("local", "stdio")):
        (tmp_path / f"{name}.json").write_text(json.dumps({name: {"type": server_type, "url": "http://placeholder"}}), encoding="utf-8")

    names = [s["name"] for s in load_supported_mcp_configs(str(tmp_path))]

    assert sorted(names) == ["old", "web"]


class _Warnings:
    """Stands in for a module logger and keeps the warnings (message and fields)."""

    def __init__(self):
        self.records = []

    def warning(self, message, **fields):
        self.records.append((message, fields))


def _dynamics(configs):
    return [s for s in configs if s["name"] == "dynamics_microservice"]


def test_shipped_dynamics_file_holds_no_host_and_allows_only_the_workflows():
    raw = (mcp_config.DEFAULT_MCPS_DIR + "/dynamics_microservice.json")
    with open(raw, encoding="utf-8") as f:
        text = f.read()

    [server] = _dynamics(load_mcp_configs())

    assert server["type"] == "streamable_http"
    assert "://" not in text and "${DYNAMICS_MCP_URL}" in text
    assert server["config"]["allowed_tools"] == [
        "customer_orders", "order_status", "customer_card", "get_guidance", "list_workflows", "get_job_result", "cancel_job",
    ]


def test_dynamics_server_is_offered_when_its_url_is_set(monkeypatch):
    monkeypatch.setenv("DYNAMICS_MCP_URL", "http://placeholder.invalid:1/mcp")

    [server] = _dynamics(load_supported_mcp_configs())

    assert server["config"]["url"] == "http://placeholder.invalid:1/mcp"


def test_a_server_whose_url_variable_is_not_set_is_skipped_with_a_warning_and_the_others_stay(monkeypatch):
    monkeypatch.delenv("DYNAMICS_MCP_URL", raising=False)
    warnings = _Warnings()
    monkeypatch.setattr(mcp_config, "logger", warnings)

    names = [s["name"] for s in load_supported_mcp_configs()]

    assert "dynamics_microservice" not in names and "aws_microservice" in names
    [(_, fields)] = [r for r in warnings.records if r[1].get("server_name") == "dynamics_microservice"]
    assert fields["variables"] == ["DYNAMICS_MCP_URL"]


class _FakeManager:
    """A client manager whose server lists the tools given."""

    def __init__(self, tool_names, allowed):
        config = {"type": "streamable_http", "url": "http://placeholder.invalid/mcp"}
        if allowed is not None:
            config["allowed_tools"] = allowed
        self.configs = {"srv": {"name": "srv", "type": "streamable_http", "config": config}}
        self._tools = [SimpleNamespace(name=n, description="", inputSchema=None) for n in tool_names]

    @asynccontextmanager
    async def session_scope(self, server_name):
        async def list_tools():
            return SimpleNamespace(tools=self._tools)
        yield SimpleNamespace(list_tools=list_tools)


def test_the_catalog_hides_tools_outside_allowed_tools_and_warns_with_their_name(monkeypatch):
    warnings = _Warnings()
    monkeypatch.setattr(tool_catalog, "logger", warnings)
    catalog = MCPToolCatalog(_FakeManager(["customer_orders", "run_query"], ["customer_orders"]))

    tools = asyncio.run(catalog.list_tools_async("srv"))

    assert [t.name for t in tools] == ["customer_orders"]
    assert asyncio.run(catalog.server_of("run_query")) is None
    assert [fields["tool_name"] for _, fields in warnings.records] == ["run_query"]


def test_a_server_file_without_allowed_tools_offers_every_tool():
    catalog = MCPToolCatalog(_FakeManager(["a", "b"], None))

    assert [t.name for t in asyncio.run(catalog.list_tools_async("srv"))] == ["a", "b"]
