# ===============================================
#  RESPONSE SCHEMAS
#  The JSON Schemas the LLM must follow, by name.
#  Read from schema/response next to the project, not from the working directory.
# ===============================================

import copy
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Sequence

SCHEMAS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'schema', 'response')

# The actions schema file. Every phase that plans or processes actions names it in its own constants.
ACTIONS_SCHEMA_FILE = "advanced/actions/actions.schema.json"


@dataclass(frozen=True)
class SchemaRef:
    """A schema property a phase uses: the file (relative to SCHEMAS_ROOT) and the top-level key inside it."""
    file: str
    key: str


# name -> file, relative to SCHEMAS_ROOT. Each file is { "<name>": {...} }, except actions.
# Only for code that looks a schema up by name. Each phase lists the files it uses in its own constants.
_SCHEMA_FILES: Dict[str, str] = {
    "intent": "advanced/intent/intent.schema.json",
    "user_goal": "advanced/user_goal/user_goal.schema.json",
    "task_category": "advanced/task_category/task_category.schema.json",
    "complexity": "basic/task_category/task_category.complexity.schema.json",
    "next_step": "advanced/next_steps/next_step.schema.json",
    "safety_and_validation": "advanced/safety_and_validation/safety_and_validation.schema.json",
    "actions": ACTIONS_SCHEMA_FILE,
}

_cache: Dict[str, Dict[str, Any]] = {}


def load_schema_file(file: str) -> Dict[str, Any]:
    """The full schema file, relative to SCHEMAS_ROOT. Each call returns its own copy."""
    if file not in _cache:
        with open(os.path.join(SCHEMAS_ROOT, file), 'r', encoding='utf-8') as f:
            _cache[file] = json.load(f)

    return copy.deepcopy(_cache[file])


def load_schema(name: str) -> Dict[str, Any]:
    """The full schema file of `name`. Each call returns its own copy."""
    if name not in _SCHEMA_FILES:
        raise KeyError(f"unknown response schema: {name}")

    return load_schema_file(_SCHEMA_FILES[name])


def schema_properties(refs: Dict[str, SchemaRef]) -> Dict[str, Dict[str, Any]]:
    """The schema of each property a phase uses: property name -> the `key` of its file."""
    return {name: load_schema_file(ref.file)[ref.key] for name, ref in refs.items()}


def actions_schema(mcp_server_names: Sequence[str] = (), file: str = ACTIONS_SCHEMA_FILE) -> Dict[str, Any]:
    """
    The actions schema. With MCP servers, `mcp_context.server_id` may only be "" (not an MCP action)
    or the name of one of them. Without servers it is a plain string.
    """
    schema = load_schema_file(file)

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
