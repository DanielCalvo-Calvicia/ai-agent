"""
Splits the full response schema into one file per node, recursively.

    python scripts/split_schemas.py           # check: lists what differs from disk (exit 1 if anything)
    python scripts/split_schemas.py --write   # write the tree, remove files that are not in it

`schema/response/<tree>/full.schema.json` (trees: `general`, `motion`) is the one place a field is edited.
Everything else under that folder is generated from it, and `tests/test_schema_tree.py` fails when the two drift apart.

Layout (a node is a property, at any depth):
- a node with children (an object, or an array of objects) gets a folder named after it. Inside:
  its own file `<path>.schema.json` (the whole subtree, which is what the phases load), one file per child,
  and for an array its `<path>.item.schema.json` (the schema of one element).
- a node without children (string, number, boolean, free-form object, a `$ref`) is one file in its parent's folder.
- `<path>` is the dotted path of keys: `actions.mcp_context.server_id`.
- A file holds `{ "<last key>": <schema> }`. The `actions` file is the exception: it is the bare array schema
  with its `$defs`, because its elements refer to themselves (`subactions`) and the pipeline loads it that way.
- Folder names are the key, except `next_step` whose folder is `next_steps` (kept: phases point at it).
"""
import json
import os
import sys
from typing import Any, Dict, List

RESPONSE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "schema", "response")
# One tree per agent answer. `general` is the answer of the text flows (identification, conversation, special); `expression` is the
# emotion reader's (the gesture that goes with a reply); `motion` is the movement
# flow's own fields (its `next_step` is the general one, so it is not repeated there).
TREES = ("general", "motion", "expression")
FULL_FILE = "full.schema.json"
FOLDER_NAMES = {"next_step": "next_steps"}
# The action element is recursive (subactions), so it lives in the root `$defs` and elements point at it.
ACTION_DEF = "action"
ACTIONS_KEY = "actions"


def _is_container(schema: Dict[str, Any]) -> bool:
    return bool(_children(schema))


def _children(schema: Dict[str, Any]) -> Dict[str, Any]:
    """The child properties of a node: its own, or those of the elements when it is an array of objects."""
    return _element(schema).get("properties", {}) if _element(schema) else schema.get("properties", {})


def _element(schema: Dict[str, Any]) -> Dict[str, Any]:
    """The schema of one element of an array node ({} for anything else)."""
    items = schema.get("items")
    return items if schema.get("type") == "array" and isinstance(items, dict) else {}


def _dump(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def _resolve(schema: Dict[str, Any], defs: Dict[str, Any]) -> Dict[str, Any]:
    """The node itself, or the definition its `items` points at (the action element)."""
    items = schema.get("items")
    if isinstance(items, dict) and "$ref" in items:
        return {**schema, "items": defs[items["$ref"].rsplit("/", 1)[-1]]}
    return schema


def _walk(path: List[str], schema: Dict[str, Any], defs: Dict[str, Any], folder: str,
          out: Dict[str, str]) -> None:
    """Adds the files of the node at `path` (and below) to `out`: relative path -> text."""
    dotted = ".".join(path)
    # Only the top-level `actions` is opened up; a `$ref` further down (subactions) is a leaf, or it would never end.
    node = _resolve(schema, defs) if len(path) == 1 else schema
    key = path[-1]

    if not _is_container(node):
        out[f"{folder}/{dotted}.schema.json"] = _dump({key: schema})
        return

    here = f"{folder}/{FOLDER_NAMES.get(key, key) if len(path) == 1 else key}"

    if len(path) == 1 and key == ACTIONS_KEY:
        out[f"{here}/{dotted}.schema.json"] = _dump({"$defs": defs, **schema})
    else:
        out[f"{here}/{dotted}.schema.json"] = _dump({key: schema})

    element = _element(node)
    if element:
        out[f"{here}/{dotted}.item.schema.json"] = _dump({"item": element})

    for child, child_schema in _children(node).items():
        _walk(path + [child], child_schema, defs, here, out)


def expected_tree(full: Dict[str, Any]) -> Dict[str, str]:
    """Every file the tree must hold, from the full schema: relative path (to `general/`) -> text."""
    defs = full.get("$defs", {})
    out: Dict[str, str] = {FULL_FILE: _dump(full)}
    for name, schema in full["properties"].items():
        _walk([name], schema, defs, "", out)

    return {path.lstrip("/"): text for path, text in out.items()}


def tree_dir(tree: str) -> str:
    return os.path.join(RESPONSE_DIR, tree)


def _on_disk(tree: str) -> Dict[str, str]:
    found: Dict[str, str] = {}
    for base, _, files in os.walk(tree_dir(tree)):
        for name in files:
            full_path = os.path.join(base, name)
            with open(full_path, "r", encoding="utf-8", newline="") as f:
                found[os.path.relpath(full_path, tree_dir(tree)).replace(os.sep, "/")] = f.read()
    return found


def differences(expected: Dict[str, str], actual: Dict[str, str]) -> List[str]:
    problems = [f"missing: {p}" for p in sorted(set(expected) - set(actual))]
    problems += [f"not in the full schema: {p}" for p in sorted(set(actual) - set(expected))]
    problems += [f"different: {p}" for p in sorted(set(expected) & set(actual)) if expected[p] != actual[p]]
    return problems


def main(argv: List[str]) -> int:
    write = "--write" in argv
    failed = False
    for tree in TREES:
        with open(os.path.join(tree_dir(tree), FULL_FILE), "r", encoding="utf-8") as f:
            expected = expected_tree(json.load(f))
        actual = _on_disk(tree)
        problems = differences(expected, actual)
        failed = failed or bool(problems)

        if not write:
            print("\n".join(f"{tree}/{p}" for p in problems) if problems
                  else f"ok: {tree}, {len(expected)} files match the full schema")
            continue

        for path in set(actual) - set(expected):
            os.remove(os.path.join(tree_dir(tree), path))
        for path, text in expected.items():
            target = os.path.join(tree_dir(tree), path)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8", newline="") as f:
                f.write(text)
        for base, dirs, files in os.walk(tree_dir(tree), topdown=False):
            if not dirs and not files:
                os.rmdir(base)
        print(f"wrote {tree}: {len(expected)} files, {len(problems)} changes")

    return 1 if failed and not write else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
