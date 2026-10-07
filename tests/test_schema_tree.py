# The schema tree under schema/response/general is generated from full.schema.json (scripts/split_schemas.py).
# These tests keep it complete: a node without its file, a file without its node, or a hand edit that drifted fails here.

import importlib.util
import json
import os

import pytest

from application.orchestration.phases.movement.motion_planner import MOTION_PLANNER
from application.orchestration.support.schemas import (
    SCHEMAS_ROOT, actions_schema, load_schema, load_schema_file, property_schema)
from domain.value_objects.movement.movement import ARMS, DIRECTIONS
from application.system_prompts.general import PROJECT_ROOT

GENERAL = os.path.join(SCHEMAS_ROOT, "general")

_spec = importlib.util.spec_from_file_location("split_schemas", os.path.join(PROJECT_ROOT, "scripts", "split_schemas.py"))
assert _spec is not None and _spec.loader is not None, "scripts/split_schemas.py could not be loaded"
split_schemas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(split_schemas)


def _full():
    with open(os.path.join(GENERAL, "full.schema.json"), "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("tree", split_schemas.TREES)
def test_every_node_has_its_file_and_every_file_has_its_node(tree):
    with open(os.path.join(SCHEMAS_ROOT, tree, "full.schema.json"), "r", encoding="utf-8") as f:
        expected = split_schemas.expected_tree(json.load(f))
    problems = split_schemas.differences(expected, split_schemas._on_disk(tree))
    assert not problems, "run `python scripts/split_schemas.py --write`:\n" + "\n".join(problems)


def test_there_is_no_basic_folder_any_more():
    assert not os.path.exists(os.path.join(SCHEMAS_ROOT, "basic"))


@pytest.mark.parametrize("name", ["intent", "user_goal", "task_category", "next_step", "safety_and_validation"])
def test_a_property_file_is_the_property_of_the_full_schema(name):
    assert property_schema(name) == _full()["properties"][name]


def test_the_actions_file_is_the_full_schemas_actions_with_its_definitions():
    assert load_schema("actions") == {"$defs": _full()["$defs"], **_full()["properties"]["actions"]}


def test_the_actions_leave_the_server_open_for_the_runtime_to_fill():
    schema = actions_schema(["aws"])
    assert schema["$defs"]["action"]["properties"]["mcp_context"]["properties"]["server_id"]["enum"] == ["", "aws"]


def test_the_full_schema_needs_every_property_and_every_nested_field():
    full = _full()
    assert set(full["required"]) == set(full["properties"])
    action = full["$defs"]["action"]
    assert "subactions" in action["properties"]
    assert set(action["required"]) == set(action["properties"]) - {"subactions"}
    mcp = action["properties"]["mcp_context"]
    assert set(mcp["required"]) == set(mcp["properties"]) == {"server_id", "tool_name", "parameters"}


def test_the_motion_schema_lists_the_arms_and_directions_the_validator_accepts():
    movement = load_schema_file("motion/movements/movements.item.schema.json")["item"]["properties"]
    assert tuple(movement["arm"]["enum"]) == ARMS
    assert tuple(movement["direction"]["enum"]) == DIRECTIONS


def test_the_motion_planner_asks_for_every_motion_field_the_spoken_reply_and_the_next_step():
    properties = MOTION_PLANNER.properties()
    assert set(properties) == set(MOTION_PLANNER.required) == {"is_motion_request", "movements", "spoken_reply", "next_step"}
    assert properties["movements"]["items"]["required"] == ["arm", "degrees", "direction"]
