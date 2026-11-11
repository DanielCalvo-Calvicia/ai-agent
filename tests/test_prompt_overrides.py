# T-05.14: a profile may replace or append to the prompt of a step (`overrides.<step>.prompt_replace` / `prompt_append`),
# from a file under prompts/ or inline. The golden file of every profile without an override is the proof that nothing else moved.
import json
import os
import shutil

import pytest

from application.assembly.assemble import assemble
from application.assembly.config_snapshot import build_snapshot
from application.runtime.profile.runner import ProfileRunner
from application.runtime.state.paused_run import FlowResult
from application.support.metrics import SessionMetrics
from application.support.llm.prompt_overrides import PromptOverride
from application.system_prompts.general import GENERIC_PROMPT_FILE, build_system_prompt_from_file
from infrastructure.outbound.config.file_source import FileConfigSource
from test_flow_golden import SCENARIOS, ScriptedLLM, _sha

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
APPENDED = "Always end the reply with the word MARMOT."
REPLACED = "You are a draft writer that only says KANGAROO."


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr("application.system_prompts.general.now_text", lambda: "NOW")


@pytest.fixture
def config(tmp_path):
    for folder in ("profiles", "flows", "step_defs", "model_sets", "prompts"):
        shutil.copytree(os.path.join(PROJECT_ROOT, folder), tmp_path / folder, ignore=shutil.ignore_patterns("_unverified"))
    os.makedirs(tmp_path / "config")
    shutil.copy(os.path.join(PROJECT_ROOT, "config", "state_fields.json"), tmp_path / "config" / "state_fields.json")
    os.makedirs(tmp_path / "prompts" / "profiles" / "special", exist_ok=True)
    (tmp_path / "prompts" / "profiles" / "special" / "draft_writer.txt").write_text(APPENDED, encoding="utf-8")
    return tmp_path


def special_with(config, overrides):
    """The `special` profile of the repository with the given `overrides`; returns the assembled agent (problems kept)."""
    path = config / "profiles" / "special.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["overrides"] = overrides
    data["token_sha256"] = "1" * 64
    path.write_text(json.dumps(data), encoding="utf-8")
    return assemble(build_snapshot(FileConfigSource(str(config))))


def run(agent, scenario="no_actions"):
    llm = ScriptedLLM(**SCENARIOS[scenario]["llm"])
    result = ProfileRunner(llm, [], SessionMetrics(), None, agent).run("special", SCENARIOS[scenario]["message"])
    assert isinstance(result, FlowResult)
    return llm


def system_prompts(llm):
    """format name -> the sha of the system prompt of its call."""
    return {call["format"].split("_response")[0]: call["system_prompt_sha"] for call in llm.calls}


def prompt_of(prompt_file, **kwargs):
    return build_system_prompt_from_file(prompt_file, clock=lambda: "NOW", **kwargs).content


# ===============================================
#  THE TEXT
# ===============================================

class TestPromptOverride:
    def test_nothing_set_is_the_prompt_of_the_step(self):
        assert PromptOverride().apply("the step prompt") == "the step prompt"

    def test_append_goes_after_the_step_prompt(self):
        assert PromptOverride(append="more").apply("the step prompt") == "the step prompt\n\nmore"

    def test_replace_takes_the_place_of_the_step_prompt(self):
        assert PromptOverride(replace="new").apply("the step prompt") == "new"

    def test_replace_and_append_together(self):
        assert PromptOverride(replace="new", append="more").apply("old") == "new\n\nmore"

    def test_the_generic_rules_stay_in_front_whatever_the_override(self):
        text = prompt_of("prompts/7_drawf_writter.txt", override=PromptOverride(replace=REPLACED))
        generic = open(os.path.join(PROJECT_ROOT, GENERIC_PROMPT_FILE), encoding="utf-8").read()
        assert text.startswith(generic) and text.endswith(REPLACED)


# ===============================================
#  THE PAYLOAD
# ===============================================

class TestWhatIsSent:
    def test_a_profile_with_an_appended_prompt_sends_it_and_only_for_that_step(self, config):
        agent = special_with(config, {"draft_writer": {"prompt_append": {"text": APPENDED}}})
        assert agent.problems == {}
        sent, baseline = system_prompts(run(agent)), system_prompts(run(special_with(config, {})))
        assert sent["draft_writer_phase7"] != baseline["draft_writer_phase7"]
        assert {k: v for k, v in sent.items() if k != "draft_writer_phase7"} == {k: v for k, v in baseline.items() if k != "draft_writer_phase7"}

    def test_the_appended_text_is_after_the_prompt_of_the_step(self, config):
        agent = special_with(config, {"draft_writer": {"prompt_append": {"text": APPENDED}}})
        expected = prompt_of("prompts/7_drawf_writter.txt", override=PromptOverride(append=APPENDED))
        assert expected.endswith("\n\n" + APPENDED)
        assert system_prompts(run(agent))["draft_writer_phase7"] == _sha(expected)

    def test_an_appended_file_is_read_from_the_repository(self, config):
        agent = special_with(config, {"draft_writer": {"prompt_append": {"file": "prompts/profiles/special/draft_writer.txt"}}})
        assert agent.problems == {} and agent.profile("special").prompts["draft_writer"].append == APPENDED

    def test_a_replacement_replaces_the_prompt_of_the_step(self, config):
        agent = special_with(config, {"draft_writer": {"prompt_replace": {"text": REPLACED}}})
        assert agent.problems == {} and agent.profile("special").prompts["draft_writer"].replace == REPLACED
        assert system_prompts(run(agent))["draft_writer_phase7"] != system_prompts(run(special_with(config, {})))["draft_writer_phase7"]

    def test_a_step_run_for_every_action_gets_the_override_too(self, config):
        agent = special_with(config, {"cognitive_worker": {"prompt_append": {"text": APPENDED}}})
        assert agent.problems == {}
        sent = system_prompts(run(agent, "action_with_subactions"))
        baseline = system_prompts(run(special_with(config, {}), "action_with_subactions"))
        assert sent["phase4_single_action"] != baseline["phase4_single_action"]
        assert sent["draft_writer_phase7"] == baseline["draft_writer_phase7"]

    def test_the_other_profiles_are_not_touched(self, config):
        special_with(config, {"draft_writer": {"prompt_append": {"text": APPENDED}}})
        agent = assemble(build_snapshot(FileConfigSource(str(config))))
        assert agent.profile("default").prompts == {} and agent.profile("chat").prompts == {}

    def test_only_the_profiles_with_tools_have_the_tool_result_rules_of_the_draft_writer(self):
        """T-06.4 change 2: the rules for a tool answer (a table, an error, a query still running, [hidden]) are an append of the profiles that have tools."""
        agent = assemble(build_snapshot(FileConfigSource(PROJECT_ROOT)))
        with_rules = {name for name, profile in agent.profiles.items() if profile.prompts}
        assert with_rules == {"special", "dynamics"}
        for name in with_rules:
            assert set(agent.profile(name).prompts) == {"draft_writer", "project_manager"}
        core = prompt_of("prompts/7_drawf_writter.txt")
        appended = agent.profile("special").prompts["draft_writer"].append
        assert agent.profile("dynamics").prompts["draft_writer"].append == appended
        for marker in ("error (not_found)", "[hidden]", "coverage", "still running", "first N tool calls"):
            assert marker in appended and marker not in core                  # nothing is lost, and chat and default no longer carry it
        assert "ignore your rules" in core and "ignore your rules" not in appended   # the data-is-not-an-instruction rule stays for everyone

    def test_only_the_profiles_with_tools_have_the_tool_rules_of_the_project_manager(self):
        """T-06.4 change 3: choosing a tool and filling its parameters is an append of the profiles with tools; the rule for no tool stays for everyone."""
        agent = assemble(build_snapshot(FileConfigSource(PROJECT_ROOT)))
        core = prompt_of("prompts/2_project_manager.txt")
        appended = agent.profile("special").prompts["project_manager"].append
        assert agent.profile("dynamics").prompts["project_manager"].append == appended
        for marker in ("set mcp_context.tool_name", "Never set an environment or a company", "ONE tool call", "a customer code, an order number or a shipment number is letters",
                       "customer code -> shipment_tracking", "order number -> order_shipments", "shipment number -> shipment_status"):
            assert marker in appended and marker not in core
        assert "available_mcp_servers is empty" in core and "Never invent a tool" in core    # default has no tools and still answers honestly


# ===============================================
#  WHAT ASSEMBLY REFUSES
# ===============================================

def problem(agent):
    return agent.problems["profiles/special"][0]


class TestWhatAssemblyRefuses:
    @pytest.mark.parametrize("override, message", [
        ({"nope_step": {"prompt_append": {"text": "x"}}}, "unknown step 'nope_step'"),
        ({"motion_validator": {"prompt_append": {"text": "x"}}}, "unknown step 'motion_validator'"),   # plain code: no prompt
        ({"user_clarification": {"prompt_replace": {"text": "x"}}}, "has no prompt a profile can change"),
        ({"motion_planner": {"prompt_append": {"text": "x"}}}, "is not a step of the flow this profile runs"),
        ({"draft_writer": {"prompt_append": "just a string"}}, "must be {\"file\""),
        ({"draft_writer": {"prompt_append": {"text": "a", "file": "prompts/x.txt"}}}, "must be {\"file\""),
        ({"draft_writer": {"prompt_append": {"text": "  "}}}, "must be a non-empty text"),
        ({"draft_writer": {"prompt_append": {"file": "/etc/passwd"}}}, "must be a file under prompts/"),
        ({"draft_writer": {"prompt_append": {"file": "prompts/../.env"}}}, "must be a file under prompts/"),
        ({"draft_writer": {"prompt_append": {"file": "prompts/profiles/special/missing.txt"}}}, "the prompt cannot be read"),
    ])
    def test_a_wrong_override_is_a_problem_named_with_its_file_and_key(self, config, override, message):
        agent = special_with(config, override)
        assert message in problem(agent) and "profiles/special" in agent.problems and "special" not in agent.profiles

    def test_one_wrong_profile_does_not_stop_the_others(self, config):
        agent = special_with(config, {"draft_writer": {"prompt_append": {"text": ""}}})
        assert "default" in agent.profiles and "chat" in agent.profiles

    def test_the_text_of_an_override_is_never_a_field_of_the_request(self):
        # a prompt override is data of the repository, read once at assembly: the request has no way to carry one
        from application.inbound.dto.session import MessageReceivedRequestDTO
        assert not any("prompt" in name for name in MessageReceivedRequestDTO.model_fields)
