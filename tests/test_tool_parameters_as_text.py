"""T-08.3: under Claude's strict structured output the open object `mcp_context.parameters` could only be `{}`, so the plan never carried
the arguments of a tool and a model had to fill them in after the plan. The schema Claude receives asks for them as TEXT that holds a
JSON object, and the mapper reads the text back. The schemas the other providers receive do not change."""
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.support.llm.schemas import actions_schema, object_schema
from application.support.tools.direct_call import direct_call_of
from application.mappers.outbound import response_mapper
from infrastructure.outbound.llm.shared.schemas.anthropic_schema import sanitize_schema
from application.mappers.outbound.response_mapper import _map_action, _parameters_of
from step_specs import make_project_manager


def find(node, name, path=""):
    """Every place a property called `name` is in a schema: (path, schema)."""
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                for prop, schema in value.items():
                    if prop == name:
                        found.append((f"{path}/{prop}", schema))
                    found += find(schema, name, f"{path}/{prop}")
            elif key != "properties":
                found += find(value, name, path)
    elif isinstance(node, list):
        for value in node:
            found += find(value, name, path)
    return found


def a_schema_with_actions():
    return object_schema(["actions"], {"actions": actions_schema(["any_server"], "general/actions/actions.schema.json")})


def test_the_schema_of_any_provider_keeps_the_open_object():
    places = find(a_schema_with_actions(), "parameters")

    assert places and all(schema.get("type") == "object" for _, schema in places)


def test_the_schema_claude_receives_asks_for_the_arguments_as_a_json_text_at_every_level():
    clean = sanitize_schema(a_schema_with_actions())

    places = find(clean, "parameters")

    assert len(places) >= 2                                                  # the action and its nested subactions
    for path, schema in places:
        assert schema["type"] == "string", path
        assert "JSON object" in schema["description"] and "Arguments to pass to the MCP tool" in schema["description"]
        assert "properties" not in schema and "additionalProperties" not in schema


def test_the_sanitizer_leaves_every_other_object_closed_as_before():
    clean = sanitize_schema(a_schema_with_actions())

    def objects(node):
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node:
                yield node
            for value in node.values():
                yield from objects(value)
        elif isinstance(node, list):
            for value in node:
                yield from objects(value)

    assert all(o.get("additionalProperties") is False for o in objects(clean))


def test_the_project_manager_schema_is_checked_the_same_way():
    spec = make_project_manager([{"name": "any_server", "type": "streamable_http", "config": {}}])
    clean = sanitize_schema(object_schema(spec.required, spec.properties()))

    assert all(schema["type"] == "string" for _, schema in find(clean, "parameters"))


ACTION = {"id": "1", "description": "read", "action_type": "mcp_tool_call", "dependencies": [], "required_inputs": [], "output": "", "error": "",
          "mcp_context": {"server_id": "any_server", "tool_name": "any_tool", "parameters": "{\"customer_no\": \"C-1\", \"page\": 2}"}}


def test_the_text_of_a_claude_answer_becomes_the_arguments_with_their_types():
    action = _map_action(ACTION)

    assert action.mcp_context.parameters == {"customer_no": "C-1", "page": 2}          # the number stays a number
    assert direct_call_of(action) is not None                                          # so the call can be made by code


def test_an_object_from_another_provider_is_taken_as_it_is():
    action = _map_action({**ACTION, "mcp_context": {**ACTION["mcp_context"], "parameters": {"customer_no": "C-1"}}})

    assert action.mcp_context.parameters == {"customer_no": "C-1"}


@pytest.mark.parametrize("value", ["", "   ", "{}", "not json", "[1, 2]", "\"text\"", "3", None, 5, []])
def test_anything_that_is_not_a_json_object_is_no_arguments(value):
    assert _parameters_of(value) == {}
    action = _map_action({**ACTION, "mcp_context": {**ACTION["mcp_context"], "parameters": value}})
    assert action.mcp_context is None and direct_call_of(action) is None               # the operator model fills them in, as before


def test_a_text_that_is_not_json_is_ignored_and_never_logged(monkeypatch):
    lines = []

    class Log:
        def warning(self, message, **fields):
            lines.append((message, fields))

    monkeypatch.setattr(response_mapper, "logger", Log())

    _parameters_of("SECRET-CUSTOMER-77 is not json")

    assert len(lines) == 1 and "SECRET-CUSTOMER-77" not in repr(lines)


def test_the_arguments_survive_the_json_round_trip_of_a_plan():
    plan = {"actions": [dict(ACTION)]}

    mapped = response_mapper._map_actions(json.loads(json.dumps(plan)))

    assert mapped[0].mcp_context.tool_name == "any_tool"
