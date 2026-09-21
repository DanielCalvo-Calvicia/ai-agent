# ===============================================
#  RESPONSE SCHEMAS
#  The JSON Schemas the LLM must follow, by name.
#  Read from schema/response next to the project, not from the working directory.
# ===============================================

import copy
import json
import os
from typing import Any, Dict, Sequence

SCHEMAS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'schema', 'response')

# name -> file, relative to SCHEMAS_ROOT. Each file is { "<name>": {...} }, except actions.
_SCHEMA_FILES: Dict[str, str] = {
    "intent": "advanced/intent/intent.schema.json",
    "user_goal": "advanced/user_goal/user_goal.schema.json",
    "task_category": "advanced/task_category/task_category.schema.json",
    "complexity": "basic/task_category/task_category.complexity.schema.json",
    "next_step": "advanced/next_steps/next_step.schema.json",
    "safety_and_validation": "advanced/safety_and_validation/safety_and_validation.schema.json",
    "actions": "advanced/actions/actions.schema.json",
}

_cache: Dict[str, Dict[str, Any]] = {}


def load_schema(name: str) -> Dict[str, Any]:
    """The full schema file of `name`. Each call returns its own copy."""
    if name not in _SCHEMA_FILES:
        raise KeyError(f"unknown response schema: {name}")

    if name not in _cache:
        with open(os.path.join(SCHEMAS_ROOT, _SCHEMA_FILES[name]), 'r', encoding='utf-8') as f:
            _cache[name] = json.load(f)

    return copy.deepcopy(_cache[name])


def actions_schema(mcp_server_names: Sequence[str] = ()) -> Dict[str, Any]:
    """
    The actions schema. With MCP servers, `mcp_context.server_id` may only be "" (not an MCP action)
    or the name of one of them. Without servers it is a plain string.
    """
    schema = load_schema("actions")

    if mcp_server_names:
        server_id = schema["$defs"]["action"]["properties"]["mcp_context"]["properties"]["server_id"]
        server_id["enum"] = [""] + list(mcp_server_names)

    return schema


def object_schema(required: Sequence[str], properties: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    The schema of a whole answer: an object with these properties.
    A property that carries its own "$defs" (the actions) gets them moved to the root, because
    its "$ref": "#/$defs/..." pointers are resolved from the root of the schema.
    """
    definitions: Dict[str, Any] = {}
    root_properties: Dict[str, Any] = {}

    for name, schema in properties.items():
        schema = dict(schema)
        definitions.update(schema.pop("$defs", {}))
        root_properties[name] = schema

    root: Dict[str, Any] = {"type": "object", "required": list(required), "properties": root_properties}
    if definitions:
        root["$defs"] = definitions

    return root


def property_schema(name: str) -> Dict[str, Any]:
    """The schema of the property `name` (the file's top-level key of the same name)."""
    return load_schema(name)[name]
