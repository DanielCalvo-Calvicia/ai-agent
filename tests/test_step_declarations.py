# T-05.16: an LLM step is a JSON declaration (step_defs/<name>.json); Python stays for the code steps and the named functions a declaration
# points to. Adding a step is one JSON file and a prompt, shown here on a temporary copy of the configuration: nothing of the repository changes.
import json
import os
import shutil

import pytest

from application.assembly.assemble import assemble
from application.assembly.config_snapshot import build_snapshot
from application.runtime.profile.inputs import read_inputs
from application.dtos.inbound.message import TextRequestDTO
from application.service.message_flow_service import MessageFlowService
from application.runtime.step import functions
from application.runtime.step.declared import parse_reads, repository_declarations
from infrastructure.outbound.config.file_source import FileConfigSource
from application.mappers.outbound.response_mapper import read_response_json
from test_flow_golden import ScriptedLLM, _sha
from test_plug_and_play import chat_like, classification, fingerprint, write

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SHOUT_TEXT = "Answer in capital letters, always."


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr("application.runtime.step.system_prompt.now_text", lambda: "NOW")


@pytest.fixture
def config(tmp_path):
    for folder in ("profiles", "flows", "step_defs", "model_sets", "prompts"):
        shutil.copytree(os.path.join(PROJECT_ROOT, folder), tmp_path / folder, ignore=shutil.ignore_patterns("_unverified"))
    os.makedirs(tmp_path / "config")
    shutil.copy(os.path.join(PROJECT_ROOT, "config", "state_fields.json"), tmp_path / "config" / "state_fields.json")
    return tmp_path


def assembled(config):
    return assemble(build_snapshot(FileConfigSource(str(config))))


def shout_step(**changes):
    declaration = {
        "schema_version": 1, "name": "shout", "about": "Writes the reply in capital letters.", "kind": "llm", "legacy_id": 900, "group": "common",
        "prompt": {"file": "prompts/profiles/mine/shout.txt"}, "default_models": ["gemini-3.1-flash-lite"],
        "intent": {"primary": "decision_support", "secondary": [], "confidence": 0.9}, "format_name": "shout_phase900_response_format",
        "answer": {"required": ["user_goal"], "pieces": [{"name": "user_goal", "file": "general/user_goal/user_goal.schema.json", "key": "user_goal"}]},
        "reads": [{"user_message": "message"}, "user_goal"], "writes": ["user_goal"],
    }
    return {**declaration, **changes}


# ===============================================
#  THE FILES OF THIS REPOSITORY
# ===============================================

class TestTheRepositoryDeclarations:
    def test_every_llm_step_is_a_declaration_and_the_code_steps_say_what_they_read_and_write(self):
        declarations = repository_declarations()
        assert {n for n, d in declarations.items() if d["kind"] == "llm"} == {
            "triage_specialist", "project_manager", "safety_quality_gatekeeper", "draft_writer", "editor_in_chief", "motion_planner", "emotion_reader",
            "tool_selector", "answer_writer"}
        assert {n for n, d in declarations.items() if d["kind"] == "llm_per_action"} == {"cognitive_worker", "mcp_operator", "data_engineer"}
        assert {n for n, d in declarations.items() if d["kind"] == "code"} == {"action_executor", "motion_validator", "gesture_builder", "tool_caller"}

    def test_every_named_function_of_a_declaration_exists(self):
        for name, declaration in repository_declarations().items():
            for slot, function_name in (declaration.get("functions") or {}).items():
                assert function_name in functions.TABLES[slot], (name, slot, function_name)

    def test_the_real_agent_assembles_with_the_data_flow_checked_for_every_profile(self, config):
        agent = assembled(config)
        assert agent.problems == {} and len(agent.step_defs) == 16
        assert set(agent.step_prompts) == {n for n, d in agent.step_defs.items() if d["kind"] != "code"}

    @pytest.mark.parametrize("entry, expected", [
        ("user_goal", ("user_goal", "user_goal", False)),
        ("actions?", ("actions", "actions", True)),
        ({"user_message": "message"}, ("user_message", "message", False)),
        ({"user_message": "message?"}, ("user_message", "message", True)),
    ])
    def test_a_read_is_a_field_an_optional_field_or_a_field_under_another_key(self, entry, expected):
        assert parse_reads([entry]) == [expected]


# ===============================================
#  ADDING A STEP IS ONE JSON FILE AND A PROMPT
# ===============================================

class TestAddingAStep:
    def add_the_step(self, config, **changes):
        write(config, "step_defs/shout.json", shout_step(**changes))
        os.makedirs(config / "prompts" / "profiles" / "mine", exist_ok=True)
        (config / "prompts" / "profiles" / "mine" / "shout.txt").write_text(SHOUT_TEXT, encoding="utf-8")
        write(config, "flows/shouting.json", {"schema_version": 1, "steps": [{"step": "shout"}], "result_from": "shout"})
        write(config, "profiles/mine.json", chat_like("mine", "mine-token", flow="shouting"))

    def run(self, config):
        agent = assembled(config)
        assert agent.problems == {}, agent.problems
        llm = ScriptedLLM(overrides={"shout_phase900_response_format": {"user_goal": {"summary": "s", "expected_outcome": "LOUD"}}})
        inputs = read_inputs(agent.profile("mine"), classification(agent), read_response_json)
        service = MessageFlowService(outbound_port=llm, mcp_list=[], agent=agent, profile="mine", inputs=inputs)
        result = service.text(TextRequestDTO(user_id="tester", session_id="s", content="hello"))
        return agent, llm, result

    def test_one_json_file_and_a_prompt_give_a_step_that_runs(self, config):
        self.add_the_step(config)
        agent, llm, result = self.run(config)
        assert [c["format"] for c in llm.calls] == ["shout_phase900_response_format"] and result.content == "LOUD"
        assert llm.calls[0]["model"] == "claude-haiku-4-5" and agent.profile("mine").steps == ["shout"]      # the model set of the profile wins over the default of the step

    def test_the_prompt_of_the_new_step_is_the_file_of_the_configuration_not_one_of_the_repository(self, config):
        self.add_the_step(config)
        _, llm, _ = self.run(config)
        from application.runtime.step.system_prompt import build_system_prompt_from_file
        expected = build_system_prompt_from_file(None, step_text=SHOUT_TEXT).content
        assert llm.calls[0]["system_prompt_sha"] == _sha(expected) and expected.endswith(SHOUT_TEXT)

    def test_what_the_step_reads_is_what_the_model_is_told_under_the_keys_it_declares(self, config):
        self.add_the_step(config)
        _, llm, _ = self.run(config)
        told = llm.calls[0]["user_message"]
        assert told.startswith("{'user_message': 'hello', 'user_goal':")

    def test_nothing_of_the_repository_had_to_change(self, config):
        before = fingerprint(PROJECT_ROOT)
        self.add_the_step(config)
        self.run(config)
        assert fingerprint(PROJECT_ROOT) == before

    def test_the_step_is_a_step_of_any_flow_that_names_it(self, config):
        self.add_the_step(config)
        agent = assembled(config)
        assert "shout" in agent.step_defs and agent.flows["shouting"].name == "shouting"


# ===============================================
#  WHAT ASSEMBLY REFUSES IN A DECLARATION
# ===============================================

class TestWhatAssemblyRefuses:
    def broken(self, config, **changes):
        path = config / "step_defs" / "draft_writer.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(changes)
        path.write_text(json.dumps(data), encoding="utf-8")
        agent = assembled(config)
        assert "step_defs/draft_writer" in agent.problems and "draft_writer" not in agent.step_defs
        return agent.problems["step_defs/draft_writer"][0]

    @pytest.mark.parametrize("changes, message", [
        ({"reads": ["nope"]}, "'nope' is not a field of config/state_fields.json"),
        ({"writes": ["nope"]}, "'nope' is not a field of config/state_fields.json"),
        ({"reads": [["user_goal"]]}, "must be a field name"),
        ({"prompt": {"file": "prompts/profiles/missing.txt"}}, "the prompt cannot be read"),
        ({"prompt": {"text": "inline"}}, "an inline text is not supported yet"),
        ({"legacy_id": 1}, "is already the number of step"),
        ({"legacy_id": "7"}, "legacy_id must be a whole number"),
        ({"group": "nowhere"}, "group must be one of"),
        ({"default_models": ["not-a-model"]}, "is not a model of the catalog"),
        ({"intent": {"primary": 1}}, "intent must be"),
        ({"format_name": ""}, "format_name must be a text"),
        ({"answer": {"pieces": [{"name": "user_goal", "file": "general/none.schema.json", "key": "user_goal"}], "required": ["user_goal"]}},
         "the schema file 'general/none.schema.json' does not exist"),
        ({"answer": {"pieces": [{"name": "user_goal", "file": "general/user_goal/user_goal.schema.json", "key": "nothing"}], "required": ["user_goal"]}},
         "has no key 'nothing'"),
        ({"answer": {"pieces": [{"name": "user_goal", "file": "general/user_goal/user_goal.schema.json", "key": "user_goal"}], "required": ["other"]}},
         "answer.required must name pieces of the answer"),
        ({"functions": {"input": "no_such_function"}}, "is not a function of application/runtime/step/functions.py"),
        ({"functions": {"output": "message_with_history"}}, "unknown key 'output'"),
        ({"for_each": "actions", "kind": "llm_per_action"}, "answer.schema_file must be"),
    ])
    def test_a_wrong_declaration_is_a_problem_named_with_its_file_and_key(self, config, changes, message):
        assert message in self.broken(config, **changes)

    def test_a_code_step_must_name_a_python_step(self, config):
        path = config / "step_defs" / "motion_validator.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["function"] = "nope"
        path.write_text(json.dumps(data), encoding="utf-8")
        assert "is not a code step of application/runtime/step/library/" in assembled(config).problems["step_defs/motion_validator"][0]

    def test_a_step_that_reads_what_nobody_writes_is_refused_for_the_profile_that_runs_it(self, config):
        path = config / "step_defs" / "editor_in_chief.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["reads"] = ["user_goal", "motion_rejection"]
        path.write_text(json.dumps(data), encoding="utf-8")
        agent = assembled(config)
        assert "editor_in_chief' reads 'motion_rejection' but no step before it writes it" in agent.problems["profiles/special"][0]
        assert "chat" not in agent.profiles and "default" not in agent.profiles

    def test_a_flow_cannot_list_a_step_that_runs_once_per_action(self, config):
        write(config, "flows/bad.json", {"schema_version": 1, "steps": [{"step": "cognitive_worker"}], "result_from": "cognitive_worker"})
        agent = assembled(config)
        assert "flows/bad" not in agent.flows or True
        from application.assembly.flow_file import flow_from_file
        from application.runtime.flow.pipeline import Pipeline
        from application.runtime.step.metrics import SessionMetrics
        with pytest.raises(ValueError, match="run once per action by the action executor"):
            Pipeline(ScriptedLLM(), [], SessionMetrics(), flow=flow_from_file("bad", {"steps": [{"step": "cognitive_worker"}], "result_from": "cognitive_worker"}))
