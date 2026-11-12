# assemble() builds the whole agent from the configuration and refuses what cannot work: one test for each problem it names
# (PR-005 section 9), the production mode (a wrong profile is disabled, the others serve) and scripts/check_agent.py.
import ast
import itertools
import dataclasses
import json
import os
import subprocess
import sys
import typing

import pytest

from application.assembly.assemble import assemble
from application.runtime.profile.assembled import DEFAULT_PROFILE
from application.assembly.config_snapshot import build_snapshot
from application.runtime.state.expression_state import ExpressionFlowState
from application.runtime.state.flow_state import FlowState
from application.runtime.state.motion_state import MotionFlowState
from domain.errors.config_error import ConfigError
from application.ports.outbound.config_ports import ConfigSourcePort
from domain.value_objects.config.loaded import Loaded
from infrastructure.outbound.config.file_source import FileConfigSource
from infrastructure.outbound.llm.shared.schemas.anthropic_schema import anthropic_schema_problems
from infrastructure.outbound.mcp.config.loader import load_tool_snapshot

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FIELDS = FileConfigSource(PROJECT_ROOT).load_state_fields().items          # the real catalog of fields
TOKEN = "a" * 64
MCP = {"dynamics": ["customer_orders", "order_status"], "mail": ["send_mail", "order_status"], "bare": None}
SCHEMA_RULES = {"anthropic": anthropic_schema_problems}


class FakeSource(ConfigSourcePort):
    """The configuration from dictionaries (and a bad file by name), so each test writes only what it checks."""

    def __init__(self, **kinds):
        self.kinds, self.bad = kinds, kinds.pop("bad", {})

    def _loaded(self, kind):
        return Loaded(items=dict(self.kinds.get(kind, {})), errors={n: m for k, n, m in self.bad if k == kind})

    def load_profiles(self): return self._loaded("profiles")
    def load_flows(self): return self._loaded("flows")
    def load_step_defs(self): return self._loaded("step_defs")
    def load_model_sets(self): return self._loaded("model_sets")
    def load_state_fields(self): return Loaded(items=dict(FIELDS))
    def load_prompt(self, name):
        if name.startswith("prompts/") and ".." not in name and "missing" not in name:
            return "a prompt"
        raise ConfigError(name)


_NUMBERS = itertools.count(1000)


def step(reads, writes, kind="llm", **extra):
    """A declaration; an `llm` one is complete (it can run): number, group, prompt, model, intent, format and answer."""
    base = {"schema_version": 1, "kind": kind, "reads": reads, "writes": writes}
    if kind == "llm":
        base.update(legacy_id=next(_NUMBERS), group="common", prompt={"file": "prompts/a_step.txt"}, default_models=["gemini-3.1-flash-lite"],
                    intent={"primary": "decision_support", "secondary": [], "confidence": 0.5}, format_name="a_step_format",
                    answer={"required": ["user_goal"], "pieces": [{"name": "user_goal", "file": "general/user_goal/user_goal.schema.json", "key": "user_goal"}]},
                    functions={"input": "message_with_history"})
    return {**base, **extra}


def flow(*steps, result_from=None, **extra):
    return {"schema_version": 1, "steps": [{"step": s} if isinstance(s, str) else s for s in steps],
            "result_from": result_from or (steps[-1] if isinstance(steps[-1], str) else steps[-1]["step"]), **extra}


def profile(**data):
    return {"schema_version": 1, "token_sha256": TOKEN, **data}


STEPS = {
    "asker": step(["message"], ["user_goal", "task_category"]),
    "draft": step(["user_goal", "message"], ["user_goal"]),
    "planner": step(["user_goal", "task_category"], ["actions"]),
    "mover": step(["message"], ["movements"], kind="code"),
}
SETS = {"cheap": {"schema_version": 1, "default": ["gemini-3.1-flash-lite"]}}
FLOWS = {"chat": flow("draft"), "task": flow("asker", "planner", "draft")}


def build(strict=False, **kinds):
    kinds.setdefault("step_defs", STEPS)
    kinds.setdefault("flows", FLOWS)
    kinds.setdefault("model_sets", SETS)
    kwargs = {"conditions": {"needs_user_input"}, "hooks": {"user_clarification", "answer_checker"}, "mcp_servers": MCP,
              "schema_rules": SCHEMA_RULES, "known_flows": {"special"}}
    kwargs.update(kinds.pop("assemble", {}))
    agent = assemble(build_snapshot(FakeSource(**kinds)), **kwargs)
    if strict:
        agent.raise_on_errors()
    return agent


def only_problem(agent, key):
    assert key in agent.problems, agent.problems
    return " | ".join(agent.problems[key])


GOOD = profile(flow="chat", inputs={"requires": ["user_goal"]}, models="cheap")


# ===============================================
#  THE CATALOG OF FIELDS
# ===============================================

class TestCatalogOfFields:
    def test_it_lists_exactly_the_fields_of_the_state_classes(self):
        fields = {f.name for cls in (FlowState, MotionFlowState, ExpressionFlowState) for f in dataclasses.fields(cls)}
        assert set(FIELDS) == fields

    def test_each_field_says_the_states_that_have_it(self):
        for name, entry in FIELDS.items():
            owners = {cls.__name__ for cls in (FlowState, MotionFlowState, ExpressionFlowState)
                      if name in {f.name for f in dataclasses.fields(cls)}}
            assert set(entry["states"]) == owners, name

    def test_the_fields_every_run_has_are_the_message_the_history_and_the_answers(self):
        assert {name for name, entry in FIELDS.items() if entry.get("always")} == {"message", "history", "answers"}

    def test_every_schema_piece_it_names_exists(self):
        for name, entry in FIELDS.items():
            if "schema" in entry:
                assert os.path.isfile(os.path.join(PROJECT_ROOT, "schema", "response", *entry["schema"].split("/"))), name


# ===============================================
#  A GOOD AGENT
# ===============================================

class TestAGoodAgent:
    def test_a_good_snapshot_assembles(self):
        agent = build(profiles={"chat": GOOD}, strict=True)
        assembled = agent.profile("chat")
        assert assembled.steps == ["draft"] and assembled.flow_name == "chat" and assembled.default_return == "text"
        assert assembled.requires == ["user_goal"] and agent.problems == {}

    def test_the_default_profile_needs_no_token(self):
        data = {"schema_version": 1, "flow": "chat", "inputs": {"requires": ["user_goal"]}}
        assert DEFAULT_PROFILE in build(profiles={DEFAULT_PROFILE: data}, strict=True).profiles

    def test_a_profile_may_list_its_own_steps(self):
        agent = build(profiles={"mine": profile(steps=["asker", "draft"])}, strict=True)
        assert agent.profile("mine").steps == ["asker", "draft"] and agent.profile("mine").flow_name is None

    def test_a_python_flow_is_accepted_until_flows_are_files(self):
        agent = build(profiles={"p": profile(flow="special")}, strict=True)
        assert agent.profile("p").steps == []                                  # only the shape of the profile was checked

    def test_a_profile_that_ends_in_a_code_step_needs_no_user_goal(self):
        build(profiles={"m": profile(steps=["mover"])}, strict=True)

    def test_the_repository_itself_assembles(self):
        snapshot = build_snapshot(FileConfigSource(PROJECT_ROOT))
        agent = assemble(snapshot,
                         mcp_servers=load_tool_snapshot(), schema_rules=SCHEMA_RULES)
        agent.raise_on_errors()


# ===============================================
#  EACH PROBLEM, NAMED WITH ITS FILE AND KEY
# ===============================================

class TestNamesAndKeys:
    def test_an_unknown_step_of_a_flow(self):
        agent = build(flows={"chat": flow("drft", result_from="drft")}, profiles={})
        assert "flows/chat.json" in only_problem(agent, "flows/chat") and "steps[0]: unknown step 'drft'" in only_problem(agent, "flows/chat")

    def test_an_unknown_key_in_a_profile(self):
        assert "unknown key 'flwo'" in only_problem(build(profiles={"p": profile(flow="chat", flwo="x")}), "profiles/p")

    def test_an_unknown_key_in_a_flow_a_step_and_a_flow_step(self):
        agent = build(flows={"chat": {**flow("draft"), "colour": 1}}, step_defs={**STEPS, "draft": {**STEPS["draft"], "tone": 1}})
        assert "unknown key 'colour'" in only_problem(agent, "flows/chat")
        assert "unknown key 'tone'" in only_problem(agent, "step_defs/draft")
        agent = build(flows={"chat": flow({"step": "draft", "colour": 1}, result_from="draft")})
        assert "steps[0]: unknown key 'colour'" in only_problem(agent, "flows/chat")

    def test_keys_that_start_with_an_underscore_are_comments(self):
        build(profiles={"p": profile(flow="chat", _note="x", inputs={"requires": ["user_goal"]})}, strict=True)

    def test_an_unknown_flow(self):
        assert "unknown flow 'nope'" in only_problem(build(profiles={"p": profile(flow="nope")}), "profiles/p")

    def test_a_profile_with_both_a_flow_and_steps_or_neither(self):
        assert "not both and not neither" in only_problem(build(profiles={"p": profile(flow="chat", steps=["draft"])}), "profiles/p")
        assert "not both and not neither" in only_problem(build(profiles={"p": profile()}), "profiles/p")

    def test_an_unknown_condition_and_an_unknown_hook(self):
        agent = build(flows={"chat": flow({"step": "draft", "pause_if": "whenever"}, on_pause="nothing", on_resume="answer_checker")})
        message = only_problem(agent, "flows/chat")
        assert "unknown condition 'whenever'" in message and "unknown hook 'nothing'" in message

    def test_the_conditions_and_hooks_a_flow_uses_are_the_ones_it_is_given(self):
        build(flows={"chat": flow({"step": "draft", "pause_if": "needs_user_input"}, on_pause="user_clarification")}, strict=True)

    def test_an_unknown_field_in_a_step_input_or_initial_state(self):
        agent = build(step_defs={**STEPS, "draft": step(["nonsense"], ["user_goal"])})
        assert "reads: 'nonsense' is not a field of config/state_fields.json" in only_problem(agent, "step_defs/draft")
        agent = build(profiles={"p": profile(flow="chat", inputs={"requires": ["nope"]}, initial_state={"also_nope": 1})})
        assert "inputs.requires: 'nope'" in only_problem(agent, "profiles/p") and "initial_state: 'also_nope'" in only_problem(agent, "profiles/p")

    def test_an_unknown_kind_of_step(self):
        assert "kind must be one of" in only_problem(build(step_defs={"x": step([], [], kind="magic")}), "step_defs/x")

    def test_default_return_and_settings_are_checked(self):
        agent = build(profiles={"p": profile(flow="chat", default_return="some", settings={"history_turns": -1, "colour": 2})})
        message = only_problem(agent, "profiles/p")
        assert "default_return must be one of text, full" in message and "settings.history_turns" in message and "unknown key 'colour'" in message


# ===============================================
#  WHAT A STEP READS
# ===============================================

class TestWhatAStepReads:
    def test_a_step_that_reads_what_nobody_writes(self):
        agent = build(profiles={"p": profile(flow="chat")})                    # `draft` reads user_goal; nothing gives it
        assert "'draft' reads 'user_goal' but no step before it writes it" in only_problem(agent, "profiles/p")

    def test_what_an_earlier_step_writes_is_enough(self):
        build(profiles={"p": profile(flow="task")}, strict=True)               # asker writes user_goal and task_category

    def test_the_order_matters(self):
        agent = build(flows={"task": flow("planner", "asker", "draft")}, profiles={"p": profile(flow="task")})
        assert "'planner' reads 'user_goal'" in only_problem(agent, "profiles/p")

    def test_a_required_input_gives_the_field_but_an_accepted_one_does_not(self):
        build(profiles={"p": profile(flow="chat", inputs={"requires": ["user_goal"]})}, strict=True)
        agent = build(profiles={"p": profile(flow="chat", inputs={"accepts": ["user_goal"]})})
        assert "'draft' reads 'user_goal'" in only_problem(agent, "profiles/p")

    def test_an_initial_value_gives_the_field(self):
        build(profiles={"p": profile(flow="chat", initial_state={"user_goal": {"expected_outcome": "x"}})}, strict=True)

    def test_a_flow_that_drops_the_step_that_provided_a_field(self):
        agent = build(flows={"task": flow("planner", "draft")}, profiles={"p": profile(flow="task")})
        assert "'planner' reads" in only_problem(agent, "profiles/p")


class TestTheResultOfAFlow:
    def test_a_flow_with_no_result_from(self):
        data = {"schema_version": 1, "steps": [{"step": "draft"}]}
        assert "no result_from" in only_problem(build(flows={"chat": data}), "flows/chat")

    def test_a_result_from_that_is_not_a_step_of_the_flow(self):
        assert "result_from 'planner' is not a step" in only_problem(build(flows={"chat": flow("draft", result_from="planner")}), "flows/chat")

    def test_a_result_step_must_write_a_user_goal(self):
        agent = build(flows={"task": flow("asker", "planner")}, profiles={"p": profile(flow="task")})
        assert "the result step 'planner' does not write user_goal" in only_problem(agent, "profiles/p")

    def test_a_result_step_of_plain_code_is_exempt(self):
        build(flows={"move": flow("mover")}, profiles={"p": profile(flow="move")}, strict=True)


# ===============================================
#  MODELS, TOKENS AND TOOLS
# ===============================================

NODE = {"type": "object", "properties": {"child": {"$ref": "#/$defs/node"}}, "$defs": {"node": {
    "type": "object", "properties": {"child": {"$ref": "#/$defs/node"}}}}}


class TestModels:
    def test_an_unknown_model(self):
        agent = build(profiles={"p": profile(flow="chat", inputs={"requires": ["user_goal"]}, models=["gemini-9-ultra"])})
        assert "profile models: 'gemini-9-ultra' is not a model of the catalog" in only_problem(agent, "profiles/p")

    def test_an_unknown_model_set(self):
        agent = build(profiles={"p": profile(flow="chat", inputs={"requires": ["user_goal"]}, models="nope")})
        assert "unknown model set 'nope'. Model sets: cheap" in only_problem(agent, "profiles/p")

    def test_an_unknown_step_in_the_overrides(self):
        agent = build(profiles={"p": profile(flow="chat", overrides={"drafter": {"models": ["gemini-3.6-flash"]}})})
        assert "overrides: unknown step 'drafter'" in only_problem(agent, "profiles/p")

    def test_a_wrong_model_set_is_reported_as_its_own_file_and_disables_the_profile_that_uses_it(self):
        agent = build(model_sets={"bad": {"schema_version": 1, "default": ["nope"]}}, profiles={"p": profile(flow="chat", models="bad")})
        assert "model_sets/bad.json" in only_problem(agent, "model_sets/bad") and "p" in agent.disabled()

    def test_a_custom_schema_that_claude_would_cut_is_refused_when_claude_may_run_the_step(self):
        steps = {**STEPS, "custom": step(["message"], ["user_goal"], answer={"schema": NODE})}
        agent = build(step_defs=steps, flows={"c": flow("custom")}, profiles={
            "p": profile(flow="c", models=["claude-haiku-4-5"])})
        assert "claude-haiku-4-5 cannot run 'custom': 'node' nests deeper than 3 levels" in only_problem(agent, "profiles/p")

    def test_every_model_of_the_list_is_checked_not_only_the_first(self):
        steps = {**STEPS, "custom": step(["message"], ["user_goal"], answer={"schema": NODE})}
        agent = build(step_defs=steps, flows={"c": flow("custom")}, profiles={
            "p": profile(flow="c", models=["gemini-3.6-flash", "claude-sonnet-5-5"])})
        assert "claude-sonnet-5-5 cannot run 'custom'" in only_problem(agent, "profiles/p")

    def test_the_same_schema_is_fine_for_a_model_that_is_not_claude_and_a_flat_schema_for_claude(self):
        steps = {**STEPS, "custom": step(["message"], ["user_goal"], answer={"schema": NODE}),
                 "flat": step(["message"], ["user_goal"], answer={"schema": {"type": "object", "properties": {"a": {"type": "string"}}}})}
        build(step_defs=steps, flows={"c": flow("custom")}, profiles={"p": profile(flow="c", models=["gemini-3.6-flash"])}, strict=True)
        build(step_defs=steps, flows={"f": flow("flat")}, profiles={"p": profile(flow="f", models=["claude-haiku-4-5"])}, strict=True)

    def test_the_rule_of_claude(self):
        assert anthropic_schema_problems({"type": "object", "properties": {"a": {"type": "string"}}}) == []
        assert len(anthropic_schema_problems(NODE)) == 1

    def test_the_action_recursion_of_the_phases_is_unrolled_on_purpose_so_the_rule_would_flag_it(self):
        from application.support.llm.schemas import ACTIONS_SCHEMA_FILE, load_schema_file
        assert anthropic_schema_problems(load_schema_file(ACTIONS_SCHEMA_FILE)) != []      # why built-in steps are not checked with it


class TestTokens:
    @pytest.mark.parametrize("token", [None, "", "short", "g" * 64, "A" * 64, "a" * 63])
    def test_a_profile_needs_the_sha256_of_its_token(self, token):
        data = {"schema_version": 1, "flow": "chat", "inputs": {"requires": ["user_goal"]}}
        if token is not None:
            data["token_sha256"] = token
        assert "token_sha256 must be the SHA-256" in only_problem(build(profiles={"p": data}), "profiles/p")

    def test_the_message_never_repeats_the_value(self):
        agent = build(profiles={"p": {"schema_version": 1, "flow": "chat", "token_sha256": "secret-value"}})
        assert "secret-value" not in " ".join(agent.all_problems())


class TestTools:
    def test_a_whole_server_and_a_tool_of_it(self):
        build(profiles={"p": profile(flow="chat", inputs={"requires": ["user_goal"]},
                                     tools={"servers": ["dynamics"], "tools": ["mail.send_mail", "customer_orders"]})}, strict=True)

    def test_an_unknown_server(self):
        agent = build(profiles={"p": profile(flow="chat", tools={"servers": ["nope"]})})
        assert "tools.servers: unknown MCP server 'nope'. Servers: dynamics, mail, bare" in only_problem(agent, "profiles/p")

    def test_a_tool_the_server_does_not_have(self):
        agent = build(profiles={"p": profile(flow="chat", tools={"tools": ["dynamics.delete_all"]})})
        assert "'dynamics' has no tool 'delete_all'" in only_problem(agent, "profiles/p")

    def test_a_server_that_lists_no_tools_cannot_be_checked_by_tool(self):
        agent = build(profiles={"p": profile(flow="chat", tools={"tools": ["bare.anything"]})})
        assert "'bare' lists no allowed tools" in only_problem(agent, "profiles/p")

    def test_a_bare_name_two_servers_share_is_ambiguous_and_an_unknown_one_is_refused(self):
        agent = build(profiles={"p": profile(flow="chat", tools={"tools": ["order_status", "ghost"]})})
        message = only_problem(agent, "profiles/p")
        assert "'order_status' is a tool of dynamics and mail: write it as server.tool" in message
        assert "no MCP server has a tool 'ghost'" in message

    def test_tools_are_checked_at_every_level(self):
        agent = build(
            profiles={"p": profile(flow="chat", overrides={"draft": {"tools": {"servers": ["x1"]}}}, flows={"chat": {"tools": {"servers": ["x2"]}}})},
            flows={"chat": {**flow("draft"), "tools": {"servers": ["x3"]}}},
            step_defs={**STEPS, "draft": {**STEPS["draft"], "tools": {"servers": ["x4"]}}})
        everything = " ".join(agent.all_problems())
        assert all(name in everything for name in ("'x1'", "'x2'", "'x3'", "'x4'"))

    def test_without_a_snapshot_of_the_tools_the_names_are_not_checked(self):
        build(profiles={"p": profile(flow="chat", inputs={"requires": ["user_goal"]}, tools={"servers": ["anything"]})},
              assemble={"mcp_servers": None}, strict=True)

    def test_the_snapshot_of_the_tools_of_the_repository(self):
        tools = load_tool_snapshot()
        assert "customer_orders" in tools["dynamics_microservice"] and "aws_microservice" in tools


# ===============================================
#  PRODUCTION: A WRONG PROFILE IS DISABLED, THE OTHERS SERVE; TESTS AND check_agent STOP
# ===============================================

class TestProductionAndStrictMode:
    def test_one_wrong_profile_does_not_stop_the_others(self):
        agent = build(profiles={"good": GOOD, "bad": profile(flow="nope")})
        assert list(agent.profiles) == ["good"]
        assert "unknown flow 'nope'" in agent.disabled()["bad"]
        with pytest.raises(KeyError):
            agent.profile("bad")

    def test_a_profile_file_that_could_not_be_read_is_disabled_and_the_others_serve(self):
        agent = build(profiles={"good": GOOD}, bad=[("profiles", "broken", "profiles/broken.json is not valid JSON: line 2")])
        assert list(agent.profiles) == ["good"] and "not valid JSON" in agent.disabled()["broken"]

    def test_a_wrong_flow_file_disables_the_profiles_that_use_it_only(self):
        agent = build(flows={**FLOWS, "chat": flow("drft", result_from="drft")}, profiles={"a": GOOD, "b": profile(flow="task")})
        assert "the flow 'chat' cannot be used" in agent.disabled()["a"] and "b" in agent.profiles

    def test_a_wrong_step_declaration_disables_the_profiles_whose_flow_uses_it(self):
        agent = build(step_defs={**STEPS, "draft": {**STEPS["draft"], "kind": "magic"}}, profiles={"a": GOOD, "m": profile(steps=["mover"])})
        assert "the step 'draft' cannot be used" in agent.disabled()["a"] and "m" in agent.profiles

    def test_a_problem_in_a_file_no_profile_uses_is_still_reported(self):
        agent = build(flows={**FLOWS, "unused": flow("drft", result_from="drft")}, profiles={"good": GOOD})
        assert "flows/unused" in agent.problems and "good" in agent.profiles and agent.disabled() == {}

    def test_strict_mode_stops_on_the_first_problem(self):
        with pytest.raises(ConfigError):
            build(profiles={"bad": profile(flow="nope")}, strict=True)


# ===============================================
#  scripts/check_agent.py
# ===============================================

def write(root, relative, data):
    path = os.path.join(str(root), *relative.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data))


def run_check(root):
    return subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "scripts", "check_agent.py"), "--root", str(root)],
                          capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=120)


class TestCheckAgentScript:
    def test_a_good_folder_says_ok_and_exits_0(self, tmp_path):
        write(tmp_path, "config/state_fields.json", {"schema_version": 1, "fields": FIELDS})
        write(tmp_path, "step_defs/draft.json", STEPS["draft"])
        os.makedirs(tmp_path / "prompts")
        (tmp_path / "prompts" / "a_step.txt").write_text("a prompt", encoding="utf-8")
        write(tmp_path, "flows/chat.json", FLOWS["chat"])
        write(tmp_path, "model_sets/cheap.json", SETS["cheap"])
        write(tmp_path, "profiles/chat.json", GOOD)
        result = run_check(tmp_path)
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip().splitlines()[-1].startswith("ok: 1 profile(s), 1 flow(s), 1 step declaration(s), 1 model set(s)")

    def test_a_wrong_folder_prints_every_problem_and_exits_1(self, tmp_path):
        write(tmp_path, "config/state_fields.json", {"schema_version": 1, "fields": FIELDS})
        write(tmp_path, "flows/chat.json", flow("drft", result_from="drft"))
        write(tmp_path, "profiles/a.json", profile(flow="nope"))
        write(tmp_path, "profiles/b.json", profile(flow="chat", colour=1))
        result = run_check(tmp_path)
        assert result.returncode == 1
        assert "error: flows/chat.json: steps[0]: unknown step 'drft'" in result.stdout
        assert "error: profiles/a.json: unknown flow 'nope'" in result.stdout
        assert "error: profiles/b.json: unknown key 'colour'" in result.stdout and "problem(s)" in result.stdout

    def test_it_reads_files_only(self):
        with open(os.path.join(PROJECT_ROOT, "scripts", "check_agent.py"), encoding="utf-8") as f:
            imported = [n.module for n in ast.walk(ast.parse(f.read())) if isinstance(n, ast.ImportFrom) and n.module]
        assert not [m for m in imported if "vercel" in m or "client_manager" in m or "tool_executor" in m]

    def test_the_repository_passes(self):
        result = run_check(PROJECT_ROOT)
        assert result.returncode == 0, result.stdout + result.stderr
