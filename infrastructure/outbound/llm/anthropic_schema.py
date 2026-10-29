# ===============================================
#  ANTHROPIC SCHEMA
#  Anthropic's OpenAI-compatible endpoint takes a `response_format` only with "strict": true. It then runs the model with
#  structured outputs, which accept a subset of JSON Schema. This turns the schema of a phase into that subset:
#    - every object gets additionalProperties: false;
#    - the keywords Anthropic refuses are removed (limits of numbers, strings and arrays);
#    - the recursive reference (an action with subactions) is unrolled to a fixed depth, because circular references are refused.
#  Only Claude models use it (vercel.py). The schemas of the phases, and what the other providers receive, do not change.
# ===============================================

import copy
from typing import Any, Dict

# An action and, inside it, two levels of subactions. Deeper nesting is not allowed by the schema Claude receives.
ACTION_DEPTH = 3

# Refused by Anthropic's structured outputs (checked against the real schemas of the phases on 2026-10-28).
UNSUPPORTED_KEYWORDS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "minLength", "maxLength",
                        "maxItems", "uniqueItems", "minContains", "maxContains")

_DROP = object()


def anthropic_response_format(response_format: Dict[str, Any], depth: int = ACTION_DEPTH) -> Dict[str, Any]:
    """The `response_format` of an OpenAI-style call as Anthropic accepts it. The argument is not modified."""
    result = copy.deepcopy(response_format)
    inner = result["json_schema"]
    inner["schema"] = sanitize_schema(inner["schema"], depth)
    inner["strict"] = True
    return result


def sanitize_schema(schema: Dict[str, Any], depth: int = ACTION_DEPTH) -> Dict[str, Any]:
    """A copy of the schema in the subset Anthropic accepts."""
    definitions: Dict[str, Any] = {}
    _collect_definitions(schema, definitions)
    return _clean(_expand(copy.deepcopy(schema), definitions, {}, depth))


def _collect_definitions(node: Any, found: Dict[str, Any]) -> None:
    if isinstance(node, dict):
        found.update(node.get("$defs", {}))
        for value in node.values():
            _collect_definitions(value, found)
    elif isinstance(node, list):
        for value in node:
            _collect_definitions(value, found)


def _expand(node: Any, definitions: Dict[str, Any], seen: Dict[str, int], depth: int) -> Any:
    """
    Inlines every $ref. A reference met more than `depth` times along one path becomes _DROP, and whatever holds it
    (the array whose items it is, then the property that holds the array) is removed.
    """
    if isinstance(node, list):
        return [item for item in (_expand(value, definitions, seen, depth) for value in node) if item is not _DROP]
    if not isinstance(node, dict):
        return node

    reference = node.get("$ref")
    if isinstance(reference, str) and reference.startswith("#/$defs/"):
        name = reference.rsplit("/", 1)[-1]
        if seen.get(name, 0) >= depth:
            return _DROP
        return _expand(copy.deepcopy(definitions[name]), definitions, {**seen, name: seen.get(name, 0) + 1}, depth)

    expanded: Dict[str, Any] = {}
    for key, value in node.items():
        if key == "$defs":
            continue
        if key == "properties":
            kept = {}
            for name, prop in value.items():
                inlined = _expand(prop, definitions, seen, depth)
                if inlined is not _DROP:
                    kept[name] = inlined
            expanded[key] = kept
            continue
        inlined = _expand(value, definitions, seen, depth)
        if inlined is _DROP:
            if key == "items":
                return _DROP
            continue
        expanded[key] = inlined

    if "properties" in expanded and isinstance(expanded.get("required"), list):
        expanded["required"] = [name for name in expanded["required"] if name in expanded["properties"]]
    return expanded


def _clean(node: Any) -> Any:
    if isinstance(node, list):
        for value in node:
            _clean(value)
        return node
    if not isinstance(node, dict):
        return node

    for keyword in UNSUPPORTED_KEYWORDS:
        node.pop(keyword, None)
    if node.get("minItems", 0) > 1:      # Anthropic accepts only 0 or 1
        node["minItems"] = 1
    if node.get("type") == "object" or "properties" in node:
        node["additionalProperties"] = False

    for key, value in node.items():
        if key == "properties":          # a mapping of names to schemas: a property may be called "minimum"
            for prop in value.values():
                _clean(prop)
        else:
            _clean(value)
    return node
