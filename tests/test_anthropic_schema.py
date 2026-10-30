"""The schema a Claude model receives: Anthropic's structured outputs accept a subset of JSON Schema (anthropic_schema.py)."""
import copy
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.orchestration.phases.common.draft_writer import DRAFT_WRITER
from application.orchestration.phases.common.editor_in_chief import EDITOR_IN_CHIEF
from application.orchestration.phases.expression.emotion_reader import EMOTION_READER
from application.orchestration.phases.identification.triage import TRIAGE
from application.orchestration.phases.movement.motion_planner import MOTION_PLANNER
from application.orchestration.phases.special.cognitive_worker import COGNITIVE_WORKER
from application.orchestration.phases.special.data_engineer import DATA_ENGINEER
from application.orchestration.phases.special.mcp_operator import MCP_OPERATOR
from application.orchestration.phases.special.project_manager import make_project_manager
from application.orchestration.phases.special.safety_gate import SAFETY_GATE
from application.orchestration.support.schemas import actions_schema, object_schema
from domain.entities.llm_request.payload import Payload
from domain.value_objects.llm_request.message import Role, create_message
from domain.value_objects.llm_request.model import get_selected_model
from domain.value_objects.llm_request.response_format import ResponseFormat
from domain.value_objects.llm_response.intent.intent import create_intent
from infrastructure.outbound.llm.anthropic_schema import (
    ACTION_DEPTH, UNSUPPORTED_KEYWORDS, anthropic_response_format, sanitize_schema)
from infrastructure.outbound.llm.config import VercelAIConfig
from infrastructure.outbound.llm.vercel import _build_options

ACTION = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "description": {"type": "string", "maxLength": 200},
        "subactions": {"type": "array", "maxItems": 10, "items": {"$ref": "#/$defs/action"}},
    },
    "required": ["id", "description", "subactions"],
}
SCHEMA = {
    "type": "object",
    "properties": {"actions": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/action"}, "$defs": {"action": ACTION}}},
    "required": ["actions"],
}


def nesting(action_schema):
    sub = action_schema["properties"].get("subactions")
    return 1 + nesting(sub["items"]) if sub else 1


def deepest(action_schema):
    sub = action_schema["properties"].get("subactions")
    return deepest(sub["items"]) if sub else action_schema


class TestTheRecursion:
    def test_the_recursive_reference_is_unrolled_to_a_fixed_depth(self):
        out = sanitize_schema(SCHEMA)
        assert "$ref" not in json.dumps(out) and "$defs" not in json.dumps(out)
        assert nesting(out["properties"]["actions"]["items"]) == ACTION_DEPTH == 3

    def test_the_deepest_action_has_no_subactions_and_does_not_require_them(self):
        last = deepest(sanitize_schema(SCHEMA)["properties"]["actions"]["items"])
        assert "subactions" not in last["properties"] and "subactions" not in last["required"]
        assert last["required"] == ["id", "description"]

    def test_the_depth_can_be_given(self):
        out = sanitize_schema(SCHEMA, depth=1)
        assert nesting(out["properties"]["actions"]["items"]) == 1

    def test_a_schema_without_references_is_only_cleaned(self):
        plain = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
        assert sanitize_schema(plain) == {**plain, "additionalProperties": False}


class TestTheSubset:
    def test_the_keywords_anthropic_refuses_are_removed(self):
        schema = {"type": "object", "required": ["n", "tags"], "properties": {
            "n": {"type": "number", "minimum": 0, "maximum": 1, "multipleOf": 0.1},
            "tags": {"type": "array", "maxItems": 3, "uniqueItems": True, "items": {"type": "string", "minLength": 1, "maxLength": 9}}}}
        out = sanitize_schema(schema)
        assert out["properties"]["n"] == {"type": "number"}
        assert out["properties"]["tags"] == {"type": "array", "items": {"type": "string"}}

    def test_a_property_called_like_a_keyword_is_kept(self):
        schema = {"type": "object", "required": ["minimum"], "properties": {"minimum": {"type": "number", "minimum": 0}}}
        out = sanitize_schema(schema)
        assert list(out["properties"]) == ["minimum"] and out["properties"]["minimum"] == {"type": "number"}

    def test_min_items_is_at_most_one(self):
        out = sanitize_schema({"type": "array", "minItems": 3, "items": {"type": "string"}})
        assert out["minItems"] == 1

    def test_every_object_forbids_other_properties_even_inside_anyof(self):
        schema = {"type": "object", "properties": {"a": {"anyOf": [{"type": "object", "properties": {"b": {"type": "string"}}}, {"type": "null"}]}}}
        out = sanitize_schema(schema)
        assert out["additionalProperties"] is False
        assert out["properties"]["a"]["anyOf"][0]["additionalProperties"] is False

    def test_the_response_format_is_strict_and_the_original_is_not_changed(self):
        original = {"type": "json_schema", "json_schema": {"name": "probe", "schema": SCHEMA}}
        before = copy.deepcopy(original)
        out = anthropic_response_format(original)
        assert original == before
        assert out["type"] == "json_schema" and out["json_schema"]["name"] == "probe" and out["json_schema"]["strict"] is True


def _walk(node):
    """Yields every schema node; the value of "properties" is a mapping of names to schemas, not a schema."""
    if isinstance(node, list):
        for value in node:
            yield from _walk(value)
    elif isinstance(node, dict):
        yield node
        for key, value in node.items():
            if key == "properties":
                for prop in value.values():
                    yield from _walk(prop)
            else:
                yield from _walk(value)


def _real_schemas():
    servers = ["dynamics_microservice"]
    whole = {1: TRIAGE, 2: make_project_manager([{"name": "dynamics_microservice", "tools": []}]), 3: SAFETY_GATE,
             7: DRAFT_WRITER, 8: EDITOR_IN_CHIEF, 20: MOTION_PLANNER, 30: EMOTION_READER}
    actions = {4: COGNITIVE_WORKER, 5: MCP_OPERATOR, 6: DATA_ENGINEER}
    found = {pid: object_schema(spec.required, spec.properties()) for pid, spec in whole.items()}
    found.update({pid: object_schema(["actions"], {"actions": actions_schema(servers, spec.schema_file)}) for pid, spec in actions.items()})
    return found


class TestTheRealPhases:
    @pytest.mark.parametrize("phase", sorted(_real_schemas()))
    def test_the_real_schema_of_the_phase_ends_in_the_subset(self, phase):
        out = sanitize_schema(_real_schemas()[phase])
        text = json.dumps(out)
        assert "$ref" not in text and "$defs" not in text
        for node in _walk(out):
            assert not set(node) & set(UNSUPPORTED_KEYWORDS), (phase, set(node) & set(UNSUPPORTED_KEYWORDS))
            assert node.get("minItems", 0) <= 1
            if node.get("type") == "object" or "properties" in node:
                assert node.get("additionalProperties") is False, phase

    def test_the_actions_of_the_planner_keep_their_fields_and_lose_only_the_deepest_subactions(self):
        out = sanitize_schema(_real_schemas()[2])
        action = out["properties"]["actions"]["items"]
        assert {"id", "description", "action_type", "dependencies"} <= set(action["properties"])
        assert nesting(action) == ACTION_DEPTH


def _payload(model_id):
    return Payload(
        intent=create_intent(primary="information_request", secondary=[], confidence=1.0),
        model=get_selected_model(model_id), system_prompt=None, message=create_message(Role.USER, "hi"),
        response_format=ResponseFormat(name="probe", schema=copy.deepcopy(SCHEMA)))


class TestTheAdapterOptions:
    def test_a_claude_model_gets_the_strict_and_sanitized_schema(self):
        options = _build_options(VercelAIConfig(), _payload("claude-haiku-4-5"))
        inner = options["response_format"]["json_schema"]
        assert inner["strict"] is True and inner["name"] == "probe"
        assert "$ref" not in json.dumps(inner["schema"]) and inner["schema"]["additionalProperties"] is False

    def test_the_other_providers_get_exactly_what_they_got_before(self):
        payload = _payload("gemini-3.1-flash-lite")
        options = _build_options(VercelAIConfig(), payload)
        assert options["response_format"] == payload.response_format.to_dict()
        assert "strict" not in options["response_format"]["json_schema"] and "$ref" in json.dumps(options["response_format"])

    def test_no_response_format_stays_no_response_format(self):
        payload = _payload("claude-haiku-4-5")
        payload.response_format = None
        assert "response_format" not in _build_options(VercelAIConfig(), payload)
