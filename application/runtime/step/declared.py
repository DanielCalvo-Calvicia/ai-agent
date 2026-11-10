# ===============================================
#  DECLARED STEPS
#  Builds what a flow runs from the JSON declaration of a step (step_defs/<name>.json, PR-005 section 3.2): the PhaseSpec of an LLM
#  step (its prompt, its answer made of existing schema pieces, what it reads and writes) or the ActionPhaseSpec of a step run once
#  per action. A declaration may read and write only fields of config/state_fields.json; when its input or result is more than a plain
#  list of fields it names a function of runtime/step/functions.py. Python stays for the `code` steps.
# ===============================================

import json
import os
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Tuple

from domain.value_objects.llm_request.model import GoogleModels

from application.runtime.state.flow_state import FlowState
from application.support.tools.mcp_servers import server_names
from application.support.llm.schemas import actions_schema, load_schema_file
from application.outbound.ports.mcp_ports import McpToolsPort
from application.runtime.step import functions
from application.runtime.step.spec import ActionPhaseSpec, PhaseSpec

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
STEP_DEFS_DIR = os.path.join(PROJECT_ROOT, "step_defs")

Reads = List[Tuple[str, str, bool]]          # (the key in what the model is told, the state field, whether the field may be missing)


def load_declarations(directory: str = STEP_DEFS_DIR) -> Dict[str, dict]:
    """name -> declaration of every step_defs/*.json that is valid JSON. A file that is not is left out (assemble() reports it)."""
    found: Dict[str, dict] = {}
    if not os.path.isdir(directory):
        return found
    for file in sorted(os.listdir(directory)):
        if not file.endswith(".json") or file.startswith("_"):
            continue
        try:
            with open(os.path.join(directory, file), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            found[file[:-len(".json")]] = data
    return found


_repository: Optional[Dict[str, dict]] = None


def repository_declarations() -> Dict[str, dict]:
    """The declarations of this repository, read once (what the registry, the catalog and the tests' helpers use)."""
    global _repository
    if _repository is None:
        _repository = load_declarations()
    return _repository


def declaration_module(name: str, declaration: dict) -> SimpleNamespace:
    """The constants a catalog entry reads (PHASE_ID, STEP_NAME, DEFAULT_MODEL, PROMPT_FILE), as a declaration gives them."""
    return SimpleNamespace(
        PHASE_ID=declaration["legacy_id"],
        STEP_NAME=name,
        DEFAULT_MODEL=GoogleModels(declaration["default_models"][0]),
        PROMPT_FILE=(declaration.get("prompt") or {}).get("file"),
        LLM=True,
        declaration=declaration,
        __name__=f"step_defs/{name}.json",
    )


# -----------------------------------------------
#  READS AND WRITES
# -----------------------------------------------

def parse_reads(entries: Optional[List[Any]]) -> Reads:
    """`"field"`, `"field?"` (it may be missing: no step before it has to write it) or `{"key": "field"}` (the model is told it under `key`)."""
    reads: Reads = []
    for entry in entries or []:
        if isinstance(entry, dict):
            key, field = next(iter(entry.items()))
        else:
            key, field = entry.rstrip("?"), entry
        reads.append((key, field.rstrip("?"), field.endswith("?")))
    return reads


def _plain_input(reads: Reads) -> Callable[[FlowState], dict]:
    return lambda state: {key: getattr(state, field) for key, field, _ in reads}


def _plain_apply(declaration: dict) -> Callable[[FlowState, Any], None]:
    fields = list(declaration.get("writes") or [])
    always = bool(declaration.get("write_always"))

    def apply(state: FlowState, response) -> None:
        for field in fields:
            value = getattr(response, field)
            if always or value:
                setattr(state, field, value)
    return apply


# -----------------------------------------------
#  THE SPECS
# -----------------------------------------------

def _intent(declaration: dict) -> Tuple[str, Tuple[str, ...], float]:
    intent = declaration["intent"]
    return intent["primary"], tuple(intent.get("secondary") or ()), float(intent["confidence"])


def _properties(pieces: List[dict], mcp_list: list, mcp_tools: Optional[McpToolsPort]) -> Dict[str, Dict[str, Any]]:
    properties: Dict[str, Dict[str, Any]] = {}
    for piece in pieces:
        if piece.get("mcp_servers"):                      # the actions: `server_id` may only name the servers the step may use
            properties[piece["name"]] = actions_schema(server_names(mcp_list, mcp_tools), piece["file"])
        else:
            properties[piece["name"]] = load_schema_file(piece["file"])[piece["key"]]
    return properties


def phase_spec_from(declaration: dict, mcp_list: Optional[list] = None, mcp_tools: Optional[McpToolsPort] = None) -> PhaseSpec:
    """The PhaseSpec of an `llm` step."""
    mcp_list = mcp_list if mcp_list is not None else []
    named = declaration.get("functions") or {}
    answer = declaration["answer"]
    if "input" in named:
        function = functions.INPUTS[named["input"]]
        build_input = lambda state: function(state, mcp_list, mcp_tools)
    else:
        build_input = _plain_input(parse_reads(declaration.get("reads")))
    apply = functions.APPLIES[named["apply"]] if "apply" in named else _plain_apply(declaration)

    if "pieces" in answer:
        required, properties = tuple(answer["required"]), (lambda: _properties(answer["pieces"], mcp_list, mcp_tools))
    else:                                           # a whole answer schema, inline or in a file of schema/response/
        whole = answer["schema"] if "schema" in answer else load_schema_file(answer["schema_file"])
        required, properties = tuple(whole.get("required", ())), (lambda: whole["properties"])

    return PhaseSpec(
        id=declaration["legacy_id"],
        step_name=declaration["name"],
        prompt_file=(declaration.get("prompt") or {}).get("file"),
        model=GoogleModels(declaration["default_models"][0]),
        intent=_intent(declaration),
        format_name=declaration["format_name"],
        required=required,
        properties=properties,
        build_input=build_input,
        apply=apply,
    )


def action_spec_from(declaration: dict) -> ActionPhaseSpec:
    """The ActionPhaseSpec of an `llm_per_action` step."""
    return ActionPhaseSpec(
        id=declaration["legacy_id"],
        step_name=declaration["name"],
        prompt_file=(declaration.get("prompt") or {}).get("file"),
        model=GoogleModels(declaration["default_models"][0]),
        intent=_intent(declaration),
        format_name=declaration["format_name"],
        schema_file=declaration["answer"]["schema_file"],
    )


def extra_function(declaration: dict) -> Callable:
    """What a per-action step is told besides the action: its named `extra` function, or nothing."""
    name = (declaration.get("functions") or {}).get("extra")
    return functions.EXTRAS[name] if name else (lambda state, mcp_list, mcp_tools, dependency_outputs, subaction_outputs: {})


# The specs of this repository's own steps, for the code and the tests that need one by name.
def phase_spec(name: str, mcp_list: Optional[list] = None, mcp_tools: Optional[McpToolsPort] = None) -> PhaseSpec:
    return phase_spec_from(repository_declarations()[name], mcp_list, mcp_tools)


def action_spec(name: str) -> ActionPhaseSpec:
    return action_spec_from(repository_declarations()[name])


def step_function(declaration: dict, runner, mcp_list: list, mcp_tools: Optional[McpToolsPort]) -> Callable[[FlowState], None]:
    """What a flow runs for an `llm` step: ask the model with the spec and write the answer into the state."""
    spec = phase_spec_from(declaration, mcp_list, mcp_tools)
    return lambda state: spec.apply(state, runner.run_phase(spec, state))
