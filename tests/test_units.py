"""Unit tests of the small modules: response mapper, schemas, provider routes, action tree, user session."""
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.orchestration.support.action_tree import (
    BLOCKED_BY_CONFIRMATION,
    action_type_of,
    mark_mcp_actions_blocked,
    subactions_of,
)
from application.orchestration.support.mcp_servers import describe_servers
from application.orchestration.phases.conversation_flow.cognitive_worker import COGNITIVE_WORKER
from application.orchestration.phases.conversation_flow.project_manager import make_project_manager
from application.orchestration.support.schemas import actions_schema, load_schema, object_schema, property_schema
from application.outbound.ports.mcp_ports import McpToolsPort
from application.service.user_session import UserSession
from domain.entities.action import create_action
from domain.value_objects.message import Role
from domain.value_objects.tool import ToolDefinition
from domain.value_objects.model import GithubModels, get_selected_model
from infrastructure.outbound.llm.config import VercelAIConfig
from infrastructure.outbound.llm.provider_models import resolve_provider_model
from infrastructure.outbound.llm.response_mapper import build_response
from infrastructure.outbound.mcp.config import load_supported_mcp_configs

USAGE = {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}


# ===============================================
#  RESPONSE MAPPER
# ===============================================

class TestResponseMapper:
    def test_plain_text(self):
        response = build_response("hello", USAGE)
        assert response.text == "hello"
        assert response.user_goal is None and response.actions is None
        assert response.tokens_usage.total_tokens == 3

    def test_empty_object_has_no_sections(self):
        response = build_response({}, USAGE)
        assert response.text is None
        assert response.intent is None and response.next_step is None and response.actions is None

    def test_sections_are_mapped(self):
        response = build_response({
            "intent": {"primary": "information_request", "secondary": ["a"], "confidence": 0.5},
            "user_goal": {"summary": "s", "expected_outcome": "o"},
            "task_category": {"domain": "system", "type": "analysis", "complexity": "low"},
            "safety_and_validation": {"sensitive": True, "requires_confirmation": False},
            "next_step": {"status": "awaiting_user_input", "requested_user_input": ["q"]},
            "constraints": {"format": "json", "language": "english", "tone": "formal", "length": "short"},
        }, USAGE)
        assert response.intent.primary == "information_request"
        assert response.user_goal.expected_outcome.get_value() == "o"
        assert response.task_category.complexity.get_value() == "low"
        assert response.safety_and_validation.sensitive.get_value() is True
        assert response.next_step.status.get_value() == "awaiting_user_input"
        assert response.next_step.requested_user_input.get_value() == ["q"]
        assert response.constraints is not None

    def test_actions_with_and_without_mcp_context(self):
        response = build_response({"actions": [
            {"id": "a1", "description": "d", "action_type": "cognitive_task"},
            {"id": "a2", "description": "d", "action_type": "mcp_tool_call", "dependencies": ["a1"],
             "mcp_context": {"server_id": "s", "tool_name": "t", "parameters": {"x": 1}}},
        ]}, USAGE)
        first, second = response.actions
        assert first.id.get_value() == "a1"
        assert first.mcp_context is None or first.mcp_context.tool_name is not None
        assert second.dependencies.get_value() == ["a1"]
        assert second.mcp_context.tool_name == "t"

    def test_null_mcp_context_is_accepted(self):
        response = build_response({"actions": [
            {"id": "a1", "description": "d", "action_type": "cognitive_task", "mcp_context": None}]}, USAGE)
        assert len(response.actions) == 1

    def test_empty_missing_information_is_ignored(self):
        assert build_response({"missing_information": {}}, USAGE).missing_information is None
        assert build_response({"missing_information": None}, USAGE).missing_information is None

    def test_missing_token_counts_are_an_error(self):
        with pytest.raises(KeyError):
            build_response("x", {})


# ===============================================
#  SCHEMAS
# ===============================================

class TestSchemas:
    @pytest.mark.parametrize("name", ["intent", "user_goal", "task_category", "complexity",
                                      "next_step", "safety_and_validation"])
    def test_property_schema_is_the_top_level_key(self, name):
        assert isinstance(property_schema(name), dict)

    def test_actions_schema_loads(self):
        assert isinstance(load_schema("actions"), dict)

    def test_unknown_schema_is_an_error(self):
        with pytest.raises(KeyError):
            load_schema("nope")

    def test_each_call_returns_its_own_copy(self):
        first = load_schema("intent")
        first["polluted"] = True
        assert "polluted" not in load_schema("intent")

    def test_loads_from_any_working_directory(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        assert property_schema("next_step")


# ===============================================
#  PROVIDER ROUTES
# ===============================================

CONFIG = VercelAIConfig(
    google_api_key="g-key", google_url="https://google.example/v1",
    mistral_api_key="m-key", mistral_url="https://mistral.example/v1",
    groq_api_key="q-key", groq_url="https://groq.example/v1",
    cohere_api_key="c-key", cohere_url="https://cohere.example/v1",
    github_api_key="h-key", github_url="https://github.example/v1",
    OLLAMA_URL="https://ollama.example/v1",
    openai_api_key="o-key", anthropic_api_key="a-key",
)


class TestProviderRoutes:
    @pytest.mark.parametrize("model_id,key,url", [
        ("gemini-3.8-flash", "g-key", "https://google.example/v1"),
        ("mistral-large-2411", "m-key", "https://mistral.example/v1"),
        ("llama-3.3-70b-versatile", "q-key", "https://groq.example/v1"),
        ("command-r7", "c-key", "https://cohere.example/v1"),
        ("llama3.3", "ollama", "https://ollama.example/v1"),
        ("gpt-4.1", "h-key", "https://github.example/v1"),
    ])
    def test_each_provider_gets_its_key_and_url(self, model_id, key, url):
        model = resolve_provider_model(get_selected_model(model_id), CONFIG, {})
        assert model._client.api_key == key
        assert str(model._client.base_url).startswith(url)

    def test_native_openai_uses_its_key(self):
        model = resolve_provider_model(get_selected_model("gpt-4o"), CONFIG, {})
        assert model._client.api_key == "o-key"

    def test_native_anthropic_uses_its_key(self):
        model = resolve_provider_model(get_selected_model("claude-3-5-haiku-latest"), CONFIG, {})
        assert model._client.api_key == "a-key"


# ===============================================
#  ACTION TREE
# ===============================================

def _action(id_, action_type="cognitive_task"):
    return create_action(id_value=id_, description_value="d", action_type_value=action_type)


class TestActionTree:
    def test_no_subactions(self):
        assert subactions_of(_action("a")) == []

    def test_subactions_from_a_dict_or_a_list(self):
        parent = _action("a")
        child = _action("b")
        parent.subactions = {"b": child}
        assert subactions_of(parent) == [child]
        parent.subactions = [child]
        assert subactions_of(parent) == [child]

    def test_action_type(self):
        assert action_type_of(_action("a", "mcp_tool_call")) == "mcp_tool_call"

    def test_blocking_marks_only_mcp_actions_at_every_level(self):
        top_mcp = _action("a", "mcp_tool_call")
        top_plain = _action("b")
        nested_mcp = _action("c", "mcp_tool_call")
        top_plain.subactions = {"c": nested_mcp}

        mark_mcp_actions_blocked([top_mcp, top_plain])

        assert top_mcp.error.get_value() == BLOCKED_BY_CONFIRMATION
        assert nested_mcp.error.get_value() == BLOCKED_BY_CONFIRMATION
        assert top_plain.error is None


# ===============================================
#  USER SESSION
# ===============================================

class TestUserSession:
    def test_remembers_both_sides_of_an_exchange(self):
        session = UserSession(session_id="s", username="u")
        session.remember("hi", "hello", max_turns=3)
        assert [(m.role, m.content) for m in session.history] == [(Role.USER, "hi"), (Role.ASSISTANT, "hello")]

    def test_an_empty_reply_is_not_stored(self):
        session = UserSession(session_id="s", username="u")
        session.remember("hi", "  ", max_turns=3)
        assert [m.role for m in session.history] == [Role.USER]

    def test_keeps_only_the_last_turns(self):
        session = UserSession(session_id="s", username="u")
        for i in range(5):
            session.remember(f"q{i}", f"a{i}", max_turns=2)
        assert [m.content for m in session.history] == ["q3", "a3", "q4", "a4"]

    def test_histories_are_not_shared_between_sessions(self):
        a, b = UserSession(session_id="a", username="u"), UserSession(session_id="b", username="u")
        a.remember("hi", "hello", max_turns=1)
        assert b.history == []


# ===============================================
#  SUBACTIONS AND REQUESTED USER INPUT (mapper)
# ===============================================

def _plain_action(id_, subactions=()):
    return {"id": id_, "description": "d", "action_type": "analysis", "subactions": list(subactions)}


class TestMapperSubactions:
    def test_nested_subactions_are_kept_at_every_level(self):
        response = build_response({"actions": [_plain_action("1", [_plain_action("1.1", [_plain_action("1.1.1")])])]}, USAGE)
        top = response.actions[0]
        child = top.subactions["1.1"]
        assert list(top.subactions) == ["1.1"]
        assert list(child.subactions) == ["1.1.1"]

    def test_an_action_without_subactions_has_none(self):
        assert build_response({"actions": [_plain_action("1")]}, USAGE).actions[0].subactions is None

    def test_at_most_ten_subactions_are_kept(self):
        subs = [_plain_action(f"1.{i}") for i in range(1, 15)]
        top = build_response({"actions": [_plain_action("1", subs)]}, USAGE).actions[0]
        assert list(top.subactions) == [f"1.{i}" for i in range(1, 11)]

    def test_the_schema_asks_for_the_same_limit(self):
        subactions = actions_schema()["$defs"]["action"]["properties"]["subactions"]
        assert subactions["maxItems"] == 10

    def test_requested_user_input_is_read(self):
        response = build_response({"next_step": {"status": "awaiting_user_input",
                                                 "requested_user_input": ["what city?"]}}, USAGE)
        assert response.next_step.requested_user_input.get_value() == ["what city?"]

    def test_mcp_context_with_arguments_is_kept(self):
        action = {**_plain_action("1"), "action_type": "mcp_tool_call",
                  "mcp_context": {"server_id": "s", "tool_name": "t", "parameters": {"a": 1}}}
        assert build_response({"actions": [action]}, USAGE).actions[0].mcp_context.tool_name == "t"


# ===============================================
#  MCP SERVERS IN THE SCHEMA AND THE INPUT
# ===============================================

class FakeTools(McpToolsPort):
    def list_tools(self, server_name):
        return [ToolDefinition(name="count_emails", description="Counts emails", parameters={"type": "object"})]


SERVERS = [{"name": "mail", "type": "sse", "config": {"url": "http://x"}}]


class TestMcpServersInSchema:
    def _server_id(self, schema):
        return schema["$defs"]["action"]["properties"]["mcp_context"]["properties"]["server_id"]

    def test_server_id_is_limited_to_the_real_servers(self):
        assert self._server_id(actions_schema(["mail", "files"]))["enum"] == ["", "mail", "files"]

    def test_without_servers_it_is_a_plain_string(self):
        assert "enum" not in self._server_id(actions_schema())

    def test_the_planner_schema_lists_the_servers(self):
        properties = make_project_manager(SERVERS).properties()
        assert self._server_id(properties["actions"])["enum"] == ["", "mail"]

    def test_the_schema_file_is_not_changed_by_a_request(self):
        actions_schema(["mail"])
        assert "enum" not in self._server_id(load_schema("actions"))

    def test_servers_are_described_with_their_tools_and_without_settings(self):
        assert describe_servers(SERVERS, FakeTools()) == [
            {"name": "mail", "tools": [{"name": "count_emails", "description": "Counts emails",
                                        "parameters": {"type": "object"}}]}]

    def test_servers_are_described_without_tools_when_there_is_no_tools_port(self):
        assert describe_servers(SERVERS, None) == [{"name": "mail", "tools": []}]

    def test_planner_input_carries_the_described_servers(self):
        from application.orchestration.state.flow_state import FlowState
        spec = make_project_manager(SERVERS, FakeTools())
        text = str(spec.build_input(FlowState(message="hi")))
        assert "count_emails" in text and "http://x" not in text


class TestSupportedMcpConfigs:
    def test_only_supported_servers_are_used(self, tmp_path):
        import json
        (tmp_path / "a.json").write_text(json.dumps({"mail": {"type": "sse", "url": "http://x/sse"}}))
        (tmp_path / "b.json").write_text(json.dumps({"fetch": {"type": "stdio", "command": "docker"}}))
        assert [s["name"] for s in load_supported_mcp_configs(str(tmp_path))] == ["mail"]


# ===============================================
#  THE SCHEMA SENT TO THE LLM IS SELF-CONTAINED
# ===============================================

def _refs(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref":
                yield value
            else:
                yield from _refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _refs(item)


def _resolves(root, ref):
    node = root
    for part in ref.removeprefix("#/").split("/"):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


class TestObjectSchema:
    def test_definitions_move_to_the_root(self):
        schema = object_schema(["actions"], {"actions": actions_schema(["mail"])})
        assert "action" in schema["$defs"]
        assert "$defs" not in schema["properties"]["actions"]

    def test_every_reference_resolves_from_the_root(self):
        schema = object_schema(["actions", "next_step"],
                               {"actions": actions_schema(["mail"]), "next_step": property_schema("next_step")})
        refs = list(_refs(schema))
        assert refs and all(_resolves(schema, r) for r in refs)

    def test_without_definitions_nothing_is_added(self):
        schema = object_schema(["intent"], {"intent": property_schema("intent")})
        assert "$defs" not in schema
        assert schema["required"] == ["intent"]

    def test_the_planner_and_the_action_calls_send_valid_references(self):
        from domain.entities.payload import Payload
        from infrastructure.outbound.llm.response_mapper import build_response
        sent = []

        class Spy:
            def ask(self, payload: Payload):
                sent.append(payload.response_format.schema)
                return build_response({"actions": [_plain_action("1")]}, USAGE)

        from application.orchestration.state.flow_state import FlowState
        from application.orchestration.support.metrics import SessionMetrics
        from application.orchestration.engine.phase_runner import PhaseRunner
        runner = PhaseRunner(Spy(), SessionMetrics(), ["mail"])
        runner.run_phase(make_project_manager(SERVERS), FlowState(message="hi"))
        runner.run_action(create_action(id_value="1", description_value="d", action_type_value="analysis"), COGNITIVE_WORKER, {})

        assert len(sent) == 2
        for schema in sent:
            assert all(_resolves(schema, r) for r in _refs(schema))
