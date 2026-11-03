# ===============================================
#  ASSEMBLE
#  Builds the whole agent from the configuration snapshot and refuses what cannot work (PR-005 section 9): an unknown name or
#  key, a profile with both or neither of `flow` and `steps`, a step that reads what nobody writes, a flow with no result,
#  a model that cannot run a step, a missing token, a tool that does not exist. Every problem names its file and its key.
#
#  It runs at start (a profile with a problem is disabled and logged, the others serve: Q07-18 C), in scripts/check_agent.py
#  and in the tests (strict: any problem stops). A flow is a file (T-05.12) and the Agent holds the Flow built from it. Until steps are
#  JSON (T-05.16) a step may have no declaration: the checks that need `reads` and `writes` skip it.
# ===============================================

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Sequence

from application.engine.config_snapshot import ConfigSnapshot
from application.engine.flow import Flow
from application.engine.flow_file import flow_from_file
from application.engine.support.model_selection import ModelResolver, check_model_set
from application.engine.support.prompt_overrides import SOURCE_KEYS, PromptOverride
from application.engine.support.schemas import load_schema_file
from application.outbound.ports.config_ports import ConfigError
from application.steps import functions as step_functions
from application.steps.catalog import PHASES
from application.steps.conditions import CONDITIONS
from application.steps.hooks import HOOKS
from application.steps.declared import parse_reads
from application.steps.registry import CODE, GROUP_ORDER, KINDS, LLM, LLM_PER_ACTION, all_steps
from domain.value_objects.llm_request.model import GoogleModels

DEFAULT_PROFILE = "default"                       # the profile of a request with no profile: it needs no token
RETURNS = ("text", "full")
TOKEN_HASH = re.compile(r"^[0-9a-f]{64}$")        # the SHA-256 of the token, in hex

PROFILE_KEYS = {"schema_version", "name", "about", "token_sha256", "flow", "steps", "inputs", "default_return", "models", "tools",
                "settings", "overrides", "flows", "initial_state", "tested"}
INPUT_KEYS = {"requires", "accepts"}
SETTING_KEYS = {"history_turns": int, "max_mcp_calls_per_message": int}
OVERRIDE_KEYS = {"models", "tools", "prompt_replace", "prompt_append"}
PROFILE_FLOW_KEYS = {"models", "tools", "steps"}
FLOW_KEYS = {"schema_version", "name", "about", "steps", "on_pause", "on_resume", "result_from", "tools", "models"}
FLOW_STEP_KEYS = {"step", "pause_if", "retry_on_status", "optional", "tools"}
STEP_DEF_KEYS = {"schema_version", "name", "about", "kind", "legacy_id", "group", "prompt", "answer", "reads", "writes", "write_always",
                 "data", "tools", "default_models", "intent", "format_name", "for_each", "function", "functions"}
ANSWER_KEYS = {"pieces", "required", "schema", "schema_file"}
PIECE_KEYS = {"name", "file", "key", "mcp_servers"}
INTENT_KEYS = {"primary", "secondary", "confidence"}
FUNCTION_KEYS = ("input", "apply", "extra")
TOOL_KEYS = {"servers", "tools"}


@dataclass
class AssembledProfile:
    name: str
    definition: dict
    flow_name: Optional[str]                 # None when the profile lists its own steps
    steps: List[str]                         # in order; empty when the flow is a Python flow (until T-05.12)
    resolver: ModelResolver
    default_return: str
    requires: List[str] = field(default_factory=list)       # inputs the request must carry
    accepts: List[str] = field(default_factory=list)
    prompts: Dict[str, PromptOverride] = field(default_factory=dict)     # step -> what the profile does to its prompt (T-05.14)
    profile_hash: str = ""                    # SHA-256 (hex) of what the profile is made of, without its token hash (T-05.15)


@dataclass
class Agent:
    profiles: Dict[str, AssembledProfile]
    problems: Dict[str, List[str]]           # "<kind>/<name>" -> every problem of that file
    flows: Dict[str, Flow] = field(default_factory=dict)     # the flow files that are fine, built
    step_defs: Dict[str, dict] = field(default_factory=dict)  # the step declarations that are fine
    step_prompts: Dict[str, str] = field(default_factory=dict)  # step -> its prompt, read through the configuration source

    def profile(self, name: str) -> AssembledProfile:
        if name not in self.profiles:
            raise KeyError(name)
        return self.profiles[name]

    def disabled(self) -> Dict[str, str]:
        """Profile name -> why it cannot be used (a profile whose file could not even be read is here too)."""
        return {key[len("profiles/"):]: "; ".join(messages) for key, messages in self.problems.items() if key.startswith("profiles/")}

    def all_problems(self) -> List[str]:
        return [message for messages in self.problems.values() for message in messages]

    def raise_on_errors(self) -> None:
        """Strict mode (tests, check_agent.py): the first problem stops everything."""
        if self.problems:
            raise ConfigError(self.all_problems()[0])


SchemaRule = Callable[[dict], List[str]]


def assemble(
    snapshot: ConfigSnapshot,
    *,
    known_flows: Collection[str] = (),
    conditions: Optional[Collection[str]] = None,
    hooks: Optional[Collection[str]] = None,
    mcp_servers: Optional[Mapping[str, Optional[Sequence[str]]]] = None,
    schema_rules: Optional[Mapping[str, SchemaRule]] = None,
) -> Agent:
    """
    `known_flows`: names of flows that exist without a file (a test's own); a profile may name them. `conditions` and `hooks`: the names
    a flow may use (the lists of steps/conditions.py and steps/hooks.py when none are given).
    `mcp_servers`: server name -> its allowed tools (None = the server lists none); None = tool names are not checked.
    `schema_rules`: provider (`anthropic`) -> a function that returns what that provider refuses in a custom answer schema.
    """
    return _Assembly(snapshot, set(known_flows), set(CONDITIONS if conditions is None else conditions),
                     set(HOOKS if hooks is None else hooks), mcp_servers, dict(schema_rules or {})).run()


class _Assembly:
    def __init__(self, snapshot, known_flows, conditions, hooks, mcp_servers, schema_rules) -> None:
        self.snapshot = snapshot
        self.known_flows = known_flows
        self.conditions = conditions
        self.hooks = hooks
        self.mcp_servers = mcp_servers
        self.schema_rules = schema_rules
        self.fields: Dict[str, dict] = snapshot.state_fields
        self.registry = {entry.name: entry for entry in all_steps() if not hasattr(entry.module, "declaration")}   # Python steps
        self.problems: Dict[str, List[str]] = {key: [message] for key, message in snapshot.errors.items()}

    # -----------------------------------------------
    #  THE WHOLE AGENT
    # -----------------------------------------------

    def run(self) -> Agent:
        for name, data in self.snapshot.model_sets.items():
            self._try(f"model_sets/{name}", lambda: check_model_set(name, data))
        for name, data in self.snapshot.step_defs.items():
            self._check_step_def(name, data)
        for name, data in self.snapshot.flows.items():
            self._check_flow_file(name, data)

        profiles: Dict[str, AssembledProfile] = {}
        for name, data in self.snapshot.profiles.items():
            assembled = self._check_profile(name, data)
            if assembled is not None and f"profiles/{name}" not in self.problems:
                profiles[name] = assembled
        flows = {name: flow_from_file(name, data) for name, data in self.snapshot.flows.items() if f"flows/{name}" not in self.problems}
        step_defs = {name: data for name, data in self.snapshot.step_defs.items() if f"step_defs/{name}" not in self.problems}
        step_prompts = {name: self.snapshot.prompt(d["prompt"]["file"]) for name, d in step_defs.items()
                        if d.get("kind") in (LLM, LLM_PER_ACTION) and isinstance(d.get("prompt"), dict) and "file" in d["prompt"]}
        return Agent(profiles, self.problems, flows, step_defs, step_prompts)

    def _problem(self, key: str, message: str) -> None:
        self.problems.setdefault(key, []).append(f"{key}.json: {message}" if "/" in key and not message.startswith(key) else message)

    def _try(self, key: str, check: Callable[[], None]) -> None:
        try:
            check()
        except ValueError as error:
            self.problems.setdefault(key, []).append(str(error))

    def _unknown_keys(self, key: str, data: dict, allowed: Collection[str], where: str = "") -> None:
        for name in data:
            if not name.startswith("_") and name not in allowed:
                self._problem(key, f"{where}unknown key {name!r}. Keys: {', '.join(sorted(allowed))}")

    # -----------------------------------------------
    #  TOOLS
    # -----------------------------------------------

    def _check_tools(self, key: str, value: Any, where: str) -> None:
        if value is None:
            return
        if not isinstance(value, dict):
            return self._problem(key, f"{where} must be an object with `servers` and `tools`")
        self._unknown_keys(key, value, TOOL_KEYS, f"{where}: ")
        if self.mcp_servers is None:
            return                                                    # no snapshot of the tools: the names are not checked

        for server in value.get("servers") or []:
            if server not in self.mcp_servers:
                self._problem(key, f"{where}.servers: unknown MCP server {server!r}. Servers: {', '.join(self.mcp_servers) or 'none'}")
        for reference in value.get("tools") or []:
            server, dot, tool = str(reference).partition(".")
            if dot:
                if server not in self.mcp_servers:
                    self._problem(key, f"{where}.tools: unknown MCP server {server!r} in {reference!r}")
                elif not self.mcp_servers[server]:
                    self._problem(key, f"{where}.tools: {server!r} lists no allowed tools, so {reference!r} cannot be checked")
                elif tool not in self.mcp_servers[server]:
                    self._problem(key, f"{where}.tools: {server!r} has no tool {tool!r}. Tools: {', '.join(self.mcp_servers[server])}")
                continue
            owners = [name for name, listed in self.mcp_servers.items() if listed and reference in listed]
            if not owners:
                self._problem(key, f"{where}.tools: no MCP server has a tool {reference!r}")
            elif len(owners) > 1:
                self._problem(key, f"{where}.tools: {reference!r} is a tool of {' and '.join(owners)}: write it as server.tool")

    # -----------------------------------------------
    #  THE STEP DECLARATIONS AND THE FLOW FILES
    # -----------------------------------------------

    def _step_names(self) -> set:
        return set(self.snapshot.step_defs) | set(self.registry)

    def _check_reserved_data(self, key: str, value: Any) -> None:
        """
        `data` of a step declaration is RESERVED for the data policy (Q07-16, not built): only its shape is checked and nothing
        reads it, so it changes nothing a profile does. A later policy has this one place to apply (T-05.15).
        """
        if value is None:
            return
        if not isinstance(value, dict) or set(value) - {"reads"}:
            return self._problem(key, "data must be an object with only `reads` (reserved for the data policy; nothing reads it yet)")
        reads = value.get("reads", [])
        if not isinstance(reads, list) or not all(isinstance(item, str) for item in reads):
            self._problem(key, "data.reads must be a list of texts (reserved for the data policy; nothing reads it yet)")

    def _check_step_def(self, name: str, data: dict) -> None:
        key = f"step_defs/{name}"
        self._unknown_keys(key, data, STEP_DEF_KEYS)
        self._check_reserved_data(key, data.get("data"))
        kind = data.get("kind")
        if kind not in KINDS:
            self._problem(key, f"kind must be one of {', '.join(KINDS)}")
        self._check_reads_and_writes(key, data)
        answer = data.get("answer")
        if answer is not None:
            if not isinstance(answer, dict):
                self._problem(key, "answer must be an object")
            else:
                self._unknown_keys(key, answer, ANSWER_KEYS, "answer: ")
        self._check_tools(key, data.get("tools"), "tools")
        if "default_models" in data:
            self._try(key, lambda: ModelResolver({"models": data["default_models"]}))
        if kind in (LLM, LLM_PER_ACTION):
            self._check_runnable(key, name, data)
        elif kind == CODE and data.get("function") is not None:
            if data["function"] not in self.registry or self.registry[data["function"]].kind != CODE:
                self._problem(key, f"function {data['function']!r} is not a code step of application/steps/. Code steps: "
                                   f"{', '.join(n for n, e in self.registry.items() if e.kind == CODE) or 'none'}")

    def _check_reads_and_writes(self, key: str, data: dict) -> None:
        for which in ("reads", "writes"):
            entries = data.get(which)
            if entries is None:
                continue
            if not isinstance(entries, list):
                self._problem(key, f"{which} must be a list")
                continue
            for entry in entries:
                shaped = (isinstance(entry, str) or (which == "reads" and isinstance(entry, dict) and len(entry) == 1
                                                     and all(isinstance(k, str) and isinstance(v, str) for k, v in entry.items())))
                if not shaped:
                    self._problem(key, f"{which}: {entry!r} must be a field name" + (" (`field?` when it may be missing) or {\"key\": \"field\"}" if which == "reads" else ""))
                    continue
                field_name = next(iter(entry.values())) if isinstance(entry, dict) else entry
                field_name = field_name.rstrip("?")
                if field_name not in self.fields:
                    self._problem(key, f"{which}: {field_name!r} is not a field of config/state_fields.json. Fields: {', '.join(self.fields)}")

    def _check_runnable(self, key: str, name: str, data: dict) -> None:
        """What an LLM step needs to run: its old number, group, prompt file, default model, intent, format name, answer and named functions."""
        if isinstance(data.get("legacy_id"), bool) or not isinstance(data.get("legacy_id"), int):
            self._problem(key, "legacy_id must be a whole number (the old phase number, a label)")
        else:
            clash = next((other for other, entry in self.registry.items() if other != name and entry.legacy_id == data["legacy_id"]), None) or \
                next((other for other, d in self.snapshot.step_defs.items() if other != name and d.get("legacy_id") == data["legacy_id"]), None)
            if clash:
                self._problem(key, f"legacy_id {data['legacy_id']} is already the number of step {clash!r}")
        if data.get("group") not in GROUP_ORDER:
            self._problem(key, f"group must be one of {', '.join(GROUP_ORDER)}")
        prompt = data.get("prompt")
        if not isinstance(prompt, dict) or set(prompt) != {"file"} or not isinstance(prompt.get("file"), str):
            self._problem(key, "prompt must be {\"file\": \"prompts/...\"} (an inline text is not supported yet)")
        else:
            try:
                self.snapshot.prompt(prompt["file"])
            except ConfigError as error:
                self._problem(key, f"prompt.file: {error}")
        models = data.get("default_models")
        if not isinstance(models, list) or not models or models[0] not in {m.value for m in GoogleModels}:
            self._problem(key, "default_models must be a list whose first model is one of the Google models of the code (the default of the step)")
        intent = data.get("intent")
        if (not isinstance(intent, dict) or set(intent) - INTENT_KEYS or not isinstance(intent.get("primary"), str)
                or not isinstance(intent.get("confidence"), (int, float)) or not isinstance(intent.get("secondary", []), list)):
            self._problem(key, "intent must be {\"primary\": text, \"secondary\": [texts], \"confidence\": number}")
        if not isinstance(data.get("format_name"), str) or not data.get("format_name"):
            self._problem(key, "format_name must be a text (the name of the answer format sent to the model)")
        answer = data.get("answer") if isinstance(data.get("answer"), dict) else {}
        if data["kind"] == LLM:
            if "pieces" in answer:
                self._check_pieces(key, answer, data)
            elif isinstance(answer.get("schema"), dict):
                pass                                                  # a whole answer schema written in the declaration
            elif isinstance(answer.get("schema_file"), str):
                self._schema_file(key, "answer.schema_file", answer["schema_file"])
            else:
                self._problem(key, "answer must have `pieces` (pieces of schema/response/), or a whole `schema` or a `schema_file`")
        else:
            if data.get("for_each") != "actions":
                self._problem(key, "for_each must be \"actions\" for a step run once per action")
            if not isinstance(answer.get("schema_file"), str):
                self._problem(key, "answer.schema_file must be the actions schema file of schema/response/")
            else:
                self._schema_file(key, "answer.schema_file", answer["schema_file"])
        for slot, function_name in (data.get("functions") or {}).items():
            if slot not in FUNCTION_KEYS:
                self._problem(key, f"functions: unknown key {slot!r}. Keys: {', '.join(FUNCTION_KEYS)}")
            elif function_name not in step_functions.TABLES[slot]:
                self._problem(key, f"functions.{slot}: {function_name!r} is not a function of application/steps/functions.py. "
                                   f"Functions: {', '.join(step_functions.TABLES[slot]) or 'none'}")
        if data["kind"] == LLM and "input" not in (data.get("functions") or {}) and not isinstance(data.get("reads"), list):
            self._problem(key, "a step with no functions.input must list the fields it reads")

    def _check_pieces(self, key: str, answer: dict, data: dict) -> None:
        pieces = answer.get("pieces")
        if not isinstance(pieces, list) or not pieces:
            return self._problem(key, "answer.pieces must be a list of pieces of schema/response/ ({\"name\", \"file\", \"key\"})")
        names = []
        for index, piece in enumerate(pieces):
            if not isinstance(piece, dict) or set(piece) - PIECE_KEYS or not isinstance(piece.get("name"), str) or not isinstance(piece.get("file"), str):
                self._problem(key, f"answer.pieces[{index}] must be {{\"name\", \"file\", \"key\"}}")
                continue
            names.append(piece["name"])
            loaded = self._schema_file(key, f"answer.pieces[{index}]", piece["file"])
            if loaded is not None and not piece.get("mcp_servers") and piece.get("key", piece["name"]) not in loaded:
                self._problem(key, f"answer.pieces[{index}]: the file {piece['file']!r} has no key {piece.get('key', piece['name'])!r}")
        required = answer.get("required")
        if not isinstance(required, list) or any(item not in names for item in required):
            self._problem(key, f"answer.required must name pieces of the answer. Pieces: {', '.join(names)}")

    def _schema_file(self, key: str, where: str, file: str) -> Optional[dict]:
        try:
            return load_schema_file(file)
        except (OSError, ValueError):
            self._problem(key, f"{where}: the schema file {file!r} does not exist in schema/response/")
            return None

    def _check_flow_file(self, name: str, data: dict) -> None:
        key = f"flows/{name}"
        self._unknown_keys(key, data, FLOW_KEYS)
        steps = data.get("steps")
        if not isinstance(steps, list) or not steps:
            return self._problem(key, "steps must be a list of steps")
        self._check_flow_steps(key, steps, data.get("on_pause"), data.get("on_resume"), data.get("result_from"))
        self._check_tools(key, data.get("tools"), "tools")
        if "models" in data:
            self._try(key, lambda: ModelResolver({"models": data["models"]}, self.snapshot.model_sets))

    def _check_flow_steps(self, key: str, steps: list, on_pause: Any, on_resume: Any, result_from: Any) -> None:
        names = []
        for index, entry in enumerate(steps):
            item = entry if isinstance(entry, dict) else {"step": entry}
            self._unknown_keys(key, item, FLOW_STEP_KEYS, f"steps[{index}]: ")
            step = item.get("step")
            names.append(step)
            if step not in self._step_names():
                self._problem(key, f"steps[{index}]: unknown step {step!r}")
            elif f"step_defs/{step}" in self.problems:
                self._problem(key, f"steps[{index}]: the step {step!r} cannot be used: {self.problems[f'step_defs/{step}'][0]}")
            condition = item.get("pause_if")
            if condition is not None and condition not in self.conditions:
                self._problem(key, f"steps[{index}]: unknown condition {condition!r}. Conditions: {', '.join(sorted(self.conditions)) or 'none'}")
            self._check_tools(key, item.get("tools"), f"steps[{index}].tools")
        for hook_key, hook in (("on_pause", on_pause), ("on_resume", on_resume)):
            if hook is not None and hook not in self.hooks:
                self._problem(key, f"{hook_key}: unknown hook {hook!r}. Hooks: {', '.join(sorted(self.hooks)) or 'none'}")
        if result_from is None:
            self._problem(key, "no result_from: say which step produces the result of the flow")
        elif result_from not in names:
            self._problem(key, f"result_from {result_from!r} is not a step of the flow")

    # -----------------------------------------------
    #  A PROFILE
    # -----------------------------------------------

    def _check_profile(self, name: str, data: dict) -> Optional[AssembledProfile]:
        key = f"profiles/{name}"
        self._unknown_keys(key, data, PROFILE_KEYS)

        if name != DEFAULT_PROFILE and not TOKEN_HASH.match(str(data.get("token_sha256", ""))):
            self._problem(key, "token_sha256 must be the SHA-256 of the token, in 64 hex characters (every profile but `default` has one)")

        flow, steps = data.get("flow"), data.get("steps")
        if (flow is None) == (steps is None):
            self._problem(key, "a profile has `flow` or `steps`, not both and not neither")
            return None

        returned = data.get("default_return", "text")
        if returned not in RETURNS:
            self._problem(key, f"default_return must be one of {', '.join(RETURNS)}")

        requires, accepts = self._check_inputs(key, data.get("inputs") or {})
        initial = data.get("initial_state") or {}
        for field_name in initial:
            if field_name not in self.fields:
                self._problem(key, f"initial_state: {field_name!r} is not a field of config/state_fields.json")
        self._check_settings(key, data.get("settings") or {})
        self._check_tools(key, data.get("tools"), "tools")
        for step, entry in (data.get("overrides") or {}).items():
            self._unknown_keys(key, entry or {}, OVERRIDE_KEYS, f"overrides.{step}: ")
            self._check_tools(key, (entry or {}).get("tools"), f"overrides.{step}.tools")
        for flow_name, entry in (data.get("flows") or {}).items():
            self._unknown_keys(key, entry or {}, PROFILE_FLOW_KEYS, f"flows.{flow_name}: ")
            self._check_tools(key, (entry or {}).get("tools"), f"flows.{flow_name}.tools")

        resolver = ModelResolver()
        try:
            resolver = ModelResolver(data, self.snapshot.model_sets)
        except ValueError as error:
            reason = next((m for k, m in self.problems.items() if k.startswith("model_sets/") and data.get("models") == k[len("model_sets/"):]), None)
            self._problem(key, f"{error}" + (f" ({reason})" if reason else ""))
        except KeyError as error:
            self._problem(key, f"unknown model set {error.args[0]!r}")

        flow_name, step_names, declared = self._resolve_flow(key, flow, steps)
        if declared:
            self._check_data_flow(key, flow_name, step_names, requires, initial)
            self._check_models(key, flow_name or "", step_names, resolver)
        prompts = self._prompt_overrides(key, data.get("overrides") or {}, step_names if declared else None)
        return AssembledProfile(name, data, flow_name, step_names, resolver, returned, requires, accepts, prompts,
                                self._profile_hash(data, flow_name, prompts))

    def _profile_hash(self, data: dict, flow_name: Optional[str], prompts: Dict[str, PromptOverride]) -> str:
        """
        The SHA-256 of the canonical JSON of what the profile is made of: its own file without the token hash (the token is a
        check against a mistake and changing it changes nothing a client gets), the flow file it runs, the model set it names
        and the text of its prompt overrides. A model, a step, a tool or a prompt that changes changes the hash; a token does not.
        """
        models = data.get("models")
        content = {
            "profile": {k: v for k, v in data.items() if k != "token_sha256"},
            "flow": self.snapshot.flows.get(flow_name) if flow_name else None,
            "model_set": self.snapshot.model_sets.get(models) if isinstance(models, str) else None,
            "prompts": {step: {"replace": p.replace, "append": p.append} for step, p in sorted(prompts.items())},
        }
        return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")).hexdigest()

    # -----------------------------------------------
    #  PROMPT OVERRIDES (T-05.14)
    # -----------------------------------------------

    def _prompt_overrides(self, key: str, overrides: dict, flow_steps: Optional[List[str]]) -> Dict[str, PromptOverride]:
        """
        `overrides.<step>.prompt_replace` and `prompt_append`: a file under prompts/ or an inline text. The step must have a prompt (it is
        not plain code), be a step of the flow (or one the action executor runs) and not be the clarification, whose prompt is part of its code.
        A profile never changes an answer schema, so a replacement cannot change the format the answer is read in.
        """
        found: Dict[str, PromptOverride] = {}
        for step, entry in overrides.items():
            parts = {kind: (entry or {}).get(kind) for kind in ("prompt_replace", "prompt_append") if (entry or {}).get(kind) is not None}
            if not parts:
                continue
            where = f"overrides.{step}"
            kind = self._kind(step)
            if kind is None:
                self._problem(key, f"{where}: unknown step {step!r}")
                continue
            if kind == CODE or step == "user_clarification":
                self._problem(key, f"{where}: the step {step!r} has no prompt a profile can change")
                continue
            if flow_steps is not None and step not in flow_steps and not (kind == LLM_PER_ACTION and "action_executor" in flow_steps):
                self._problem(key, f"{where}: {step!r} is not a step of the flow this profile runs")
                continue
            texts = {which: self._prompt_text(key, f"{where}.{which}", value) for which, value in parts.items()}
            if all(text is not None for text in texts.values()):
                found[step] = PromptOverride(texts.get("prompt_replace"), texts.get("prompt_append"))
        return found

    def _prompt_text(self, key: str, where: str, value: Any) -> Optional[str]:
        if not isinstance(value, dict) or set(value) - set(SOURCE_KEYS) or len(value) != 1:
            self._problem(key, f"{where} must be {{\"file\": \"prompts/...\"}} or {{\"text\": \"...\"}}")
            return None
        source, content = next(iter(value.items()))
        if not isinstance(content, str) or not content.strip():
            self._problem(key, f"{where}.{source} must be a non-empty text")
            return None
        if source == "text":
            return content
        if not content.replace("\\", "/").startswith("prompts/") or ".." in content.replace("\\", "/").split("/"):
            self._problem(key, f"{where}.file must be a file under prompts/ (for example prompts/profiles/<profile>/<step>.txt)")
            return None
        try:
            return self.snapshot.prompt(content)
        except ConfigError as error:
            self._problem(key, f"{where}.file: {error}")
            return None

    def _check_inputs(self, key: str, inputs: dict):
        self._unknown_keys(key, inputs, INPUT_KEYS, "inputs: ")
        lists = {}
        for which in ("requires", "accepts"):
            lists[which] = list(inputs.get(which) or [])
            for field_name in lists[which]:
                if field_name not in self.fields:
                    self._problem(key, f"inputs.{which}: {field_name!r} is not a field of config/state_fields.json")
        return lists["requires"], lists["accepts"]

    def _check_settings(self, key: str, settings: dict) -> None:
        self._unknown_keys(key, settings, SETTING_KEYS, "settings: ")
        for setting, value in settings.items():
            expected = SETTING_KEYS.get(setting)
            if expected and (isinstance(value, bool) or not isinstance(value, expected) or value < 0):
                self._problem(key, f"settings.{setting} must be a whole number, zero or more")

    def _resolve_flow(self, key: str, flow: Any, steps: Any):
        """(the name of the flow or None, the steps in order, whether they are declared as data). Reports an unknown flow or step."""
        if steps is not None:                                         # the profile lists its own steps: an anonymous flow
            if not isinstance(steps, list) or not steps:
                self._problem(key, "steps must be a list of steps")
                return None, [], False
            last = steps[-1]["step"] if isinstance(steps[-1], dict) else steps[-1]
            self._check_flow_steps(key, steps, None, None, last)
            return None, [(s["step"] if isinstance(s, dict) else s) for s in steps], True

        if flow in self.snapshot.flows:
            if f"flows/{flow}" in self.problems:
                self._problem(key, f"the flow {flow!r} cannot be used: {self.problems[f'flows/{flow}'][0]}")
                return flow, [], False
            return flow, [(s["step"] if isinstance(s, dict) else s) for s in self.snapshot.flows[flow]["steps"]], True
        if flow in self.known_flows:
            return flow, [], False                                    # a Python flow: only the shape of the profile is checked
        why = self.problems.get(f"flows/{flow}")
        self._problem(key, f"the flow {flow!r} cannot be used: {why[0]}" if why else f"unknown flow {flow!r}")
        return flow, [], False

    # -----------------------------------------------
    #  WHAT A PROFILE NEEDS TO WORK
    # -----------------------------------------------

    def _declaration(self, step: str) -> Optional[dict]:
        definition = self.snapshot.step_defs.get(step)
        if definition is not None and isinstance(definition.get("reads"), list) and isinstance(definition.get("writes"), list):
            return definition
        return None

    def _kind(self, step: str) -> Optional[str]:
        definition = self.snapshot.step_defs.get(step)
        if definition is not None:
            return definition.get("kind")
        return self.registry[step].kind if step in self.registry else None

    def _check_data_flow(self, key: str, flow_name: Optional[str], steps: List[str], requires: List[str], initial: dict) -> None:
        """Every step reads only what an input, an initial value or an earlier step provides; the result carries a user_goal."""
        if any(self._declaration(step) is None for step in steps):
            return                                                    # a step with no declaration: nothing can be said (until T-05.16)

        available = {name for name, entry in self.fields.items() if entry.get("always")} | set(requires) | set(initial)
        for step in steps:
            definition = self._declaration(step)
            for _, field_name, optional in parse_reads(definition["reads"]):
                if not optional and field_name not in available:
                    self._problem(key, f"{flow_name or 'steps'}: {step!r} reads {field_name!r} but no step before it writes it, "
                                       f"no required input gives it and no initial_state gives it")
            available |= {w.rstrip("?") for w in definition["writes"]}

        result = self._result_step(flow_name, steps)
        declaration = self._declaration(result) if result in steps else None
        if declaration is not None and self._kind(result) != CODE and "user_goal" not in declaration["writes"]:
            self._problem(key, f"the result step {result!r} does not write user_goal: the session keeps the input and the output of a request in it")

    def _result_step(self, flow_name: Optional[str], steps: List[str]) -> Optional[str]:
        if flow_name is not None and flow_name in self.snapshot.flows:
            return self.snapshot.flows[flow_name].get("result_from")
        return steps[-1] if steps else None

    def _check_models(self, key: str, flow_name: str, steps: List[str], resolver: ModelResolver) -> None:
        """A custom answer schema must pass the rules of every provider that may run the step (Claude's nesting limit, ADR-013)."""
        for step in steps:
            schema = self._custom_schema(key, step)
            if schema is None:
                continue
            info = next((p for p in PHASES.values() if p.step_name == step), None)
            chosen = resolver.source_for(flow_name, step) != "step default"
            if info is None and not chosen:
                continue                                              # no list and no code default: nothing to check against
            for model in resolver.models_for(flow_name, step, info.default_model if info else GoogleModels.GEMINI_3_1_FLASH_LITE):
                rule = self.schema_rules.get("anthropic") if model.is_anthropic() else None
                for problem in (rule(schema) if rule else []):
                    self._problem(key, f"{model.id} cannot run {step!r}: {problem}")

    def _custom_schema(self, key: str, step: str) -> Optional[dict]:
        answer = (self.snapshot.step_defs.get(step) or {}).get("answer") or {}
        if isinstance(answer.get("schema"), dict):
            return answer["schema"]
        if isinstance(answer.get("schema_file"), str):
            try:
                return load_schema_file(answer["schema_file"])
            except OSError:
                self._problem(key, f"step {step!r}: the schema file {answer['schema_file']!r} does not exist")
        return None
