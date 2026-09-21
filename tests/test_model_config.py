"""Which LLM each step uses: the config file, the profiles, the variables, and the table of Gemini models."""
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.orchestration.metrics import PHASE_NAMES
from application.orchestration.model_selection import (
    MODELS_FILE_VARIABLE, STEP_NAMES, choose, effective_models, load_config, model_for_phase, models_file,
)
from domain.value_objects.model import GithubModels, get_selected_model
from model_table import (CONFIG_PATH, DOC_PATH, LEVELS, MODELS_PATH, best_options, blended, load_models, markdown,
                         per_call, per_message, read_config, set_profile, set_step)

from test_flow_golden import MCP_LIST, SCENARIOS, ScriptedLLM

DEFAULT = GithubModels.GPT_4_1
TRIAGE, PLANNER, GATE, WORKER, TOOLS, CLEANER, DRAFT, EDITOR, CHECKER, QUESTION = 1, 2, 3, 4, 5, 6, 7, 8, 9, 99


@pytest.fixture
def config(tmp_path, monkeypatch):
    """Writes a config file and points the agent to it. Returns a function to (re)write it."""
    path = tmp_path / "step_models.json"

    def write(data):
        path.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setenv(MODELS_FILE_VARIABLE, str(path))
        os.utime(path, (os.path.getmtime(path) + write.calls, os.path.getmtime(path) + write.calls))   # a new mtime
        write.calls += 1
        return path

    write.calls = 1
    return write


# ===============================================
#  ORDER OF PRECEDENCE
# ===============================================

class TestPrecedence:
    def test_without_a_config_file_the_defaults_of_the_code_are_used(self):
        assert not os.path.exists(models_file())
        assert model_for_phase(TRIAGE, GithubModels.GPT_4_1_MINI).id == "gpt-4.1-mini"
        assert model_for_phase(PLANNER, DEFAULT).id == "gpt-4.1"
        assert choose(PLANNER) == (None, "code default")

    def test_a_step_of_the_file_sets_that_step_only(self, config):
        config({"steps": {"project_manager": "gemini-3.8-flash"}})
        assert model_for_phase(PLANNER, DEFAULT).id == "gemini-3.8-flash"
        assert model_for_phase(GATE, DEFAULT).id == "gpt-4.1"

    def test_the_default_of_the_profile_covers_every_step(self, config):
        config({"profile": "p", "profiles": {"p": {"default": "gemini-2.5-flash-lite"}}})
        assert [model_for_phase(n, DEFAULT).id for n in (TRIAGE, PLANNER, CHECKER, QUESTION)] == ["gemini-2.5-flash-lite"] * 4

    def test_a_step_of_the_profile_beats_the_default_of_the_profile(self, config):
        config({"profile": "p", "profiles": {"p": {"default": "gemini-2.5-flash-lite", "project_manager": "gemini-3.8-flash"}}})
        assert model_for_phase(PLANNER, DEFAULT).id == "gemini-3.8-flash"
        assert model_for_phase(GATE, DEFAULT).id == "gemini-2.5-flash-lite"

    def test_steps_beat_the_profile(self, config):
        config({"profile": "p", "steps": {"project_manager": "gemini-3.1-pro-preview"},
                "profiles": {"p": {"default": "gemini-2.5-flash-lite", "project_manager": "gemini-3.8-flash"}}})
        assert model_for_phase(PLANNER, DEFAULT).id == "gemini-3.1-pro-preview"

    def test_the_variable_beats_everything(self, config, monkeypatch):
        config({"profile": "p", "steps": {"project_manager": "gemini-3.1-pro-preview"},
                "profiles": {"p": {"default": "gemini-2.5-flash-lite"}}})
        monkeypatch.setenv("AI_AGENT_MODEL_PHASE_2", "gemini-3.5-flash-lite")
        assert model_for_phase(PLANNER, DEFAULT).id == "gemini-3.5-flash-lite"
        assert choose(PLANNER) == ("gemini-3.5-flash-lite", "env AI_AGENT_MODEL_PHASE_2")

    def test_null_and_empty_values_are_skipped(self, config):
        config({"profile": "p", "steps": {"project_manager": None, "triage_specialist": ""},
                "profiles": {"p": {"default": "gemini-2.5-flash", "project_manager": None}}})
        assert model_for_phase(PLANNER, DEFAULT).id == "gemini-2.5-flash"
        assert model_for_phase(TRIAGE, DEFAULT).id == "gemini-2.5-flash"

    def test_changing_the_profile_changes_every_step_at_once(self, config):
        data = {"profile": "cheap", "profiles": {"cheap": {"default": "gemini-2.5-flash-lite"},
                                                 "strong": {"default": "gemini-3.8-flash"}}}
        config(data)
        assert model_for_phase(GATE, DEFAULT).id == "gemini-2.5-flash-lite"
        config({**data, "profile": "strong"})
        assert model_for_phase(GATE, DEFAULT).id == "gemini-3.8-flash"

    def test_each_name_of_a_step_is_its_phase(self, config):
        names = {name: f"gemini-3.{i}-flash" for i, name in zip((6, 7, 8, 6, 7, 8, 6, 7, 8, 6), STEP_NAMES)}
        config({"steps": names})
        for phase, name in PHASE_NAMES.items():
            assert model_for_phase(phase, DEFAULT).id == names[name], name

    def test_the_source_of_each_choice_is_reported(self, config, monkeypatch):
        config({"profile": "p", "steps": {"project_manager": "gemini-3.8-flash"},
                "profiles": {"p": {"default": "gemini-2.5-flash", "draft_writer": "gemini-3.1-flash-lite"}}})
        monkeypatch.setenv("AI_AGENT_MODEL_PHASE_9", "gemini-2.5-flash-lite")
        sources = {name: source for name, (_, source) in effective_models().items()}
        assert sources["project_manager"] == "config steps"
        assert sources["draft_writer"] == "profile p"
        assert sources["triage_specialist"] == "profile p default"
        assert sources["answer_checker"] == "env AI_AGENT_MODEL_PHASE_9"

    def test_a_file_that_changes_is_read_again(self, config):
        config({"steps": {"project_manager": "gemini-3.8-flash"}})
        assert model_for_phase(PLANNER, DEFAULT).id == "gemini-3.8-flash"
        config({"steps": {"project_manager": "gemini-2.5-flash"}})
        assert model_for_phase(PLANNER, DEFAULT).id == "gemini-2.5-flash"

    def test_keys_that_start_with_an_underscore_are_ignored(self, config):
        config({"_help": "x", "_other": {"a": 1}, "steps": {"_note": "anything", "project_manager": "gemini-3.8-flash"},
                "profile": "p", "profiles": {"p": {"_about": "text", "default": "gemini-2.5-flash"}}})
        assert model_for_phase(PLANNER, DEFAULT).id == "gemini-3.8-flash"


# ===============================================
#  MISTAKES ARE REPORTED, NOT IGNORED
# ===============================================

class TestMistakes:
    def test_an_unknown_step_lists_the_valid_ones(self, config):
        config({"steps": {"project_manger": "gemini-2.5-flash"}})            # a typo
        with pytest.raises(ValueError, match="unknown step 'project_manger'.*triage_specialist"):
            model_for_phase(PLANNER, DEFAULT)

    def test_an_unknown_model_names_the_place_of_the_mistake(self, config):
        config({"steps": {"project_manager": "gemini-9-ultra"}})
        with pytest.raises(ValueError, match="steps.project_manager: 'gemini-9-ultra' is not a model of the catalog"):
            model_for_phase(GATE, DEFAULT)                                      # even for another step: the file is wrong

    def test_an_unknown_model_in_a_profile(self, config):
        config({"profile": "p", "profiles": {"p": {"default": "nope"}}})
        with pytest.raises(ValueError, match="profiles.p.default: 'nope'"):
            load_config()

    def test_a_profile_that_does_not_exist(self, config):
        config({"profile": "missing", "profiles": {"p": {}}})
        with pytest.raises(ValueError, match="profile 'missing' is not defined. Profiles: p"):
            load_config()

    def test_a_file_that_is_not_json(self, config, tmp_path, monkeypatch):
        path = tmp_path / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        monkeypatch.setenv(MODELS_FILE_VARIABLE, str(path))
        with pytest.raises(ValueError, match="is not valid JSON"):
            load_config()

    def test_a_wrong_model_in_the_variable_is_reported(self, monkeypatch):
        monkeypatch.setenv("AI_AGENT_MODEL_PHASE_1", "not-a-model")
        with pytest.raises(ValueError, match="AI_AGENT_MODEL_PHASE_1"):
            model_for_phase(TRIAGE, DEFAULT)


# ===============================================
#  THE CHOICE REACHES THE LLM CALLS
# ===============================================

class TestReachesTheCalls:
    def test_every_step_calls_the_model_of_the_file(self, config):
        config({"steps": {"triage_specialist": "gemini-3.5-flash-lite", "project_manager": "gemini-3.8-flash",
                          "safety_quality_gatekeeper": "gemini-3.1-flash-lite", "cognitive_worker": "gemini-2.5-flash",
                          "mcp_operator": "gemini-3.7-flash", "data_engineer": "gemini-2.5-flash-lite",
                          "draft_writer": "gemini-3.6-flash", "editor_in_chief": "gemini-3.1-pro-preview"}})
        scenario = SCENARIOS["full_path_with_mcp"]
        llm = ScriptedLLM(**scenario["llm"])
        from application.service.message_flow_service import MessageFlowService
        from application.inbound.dto.message import TextRequestDTO
        MessageFlowService(outbound_port=llm, mcp_list=MCP_LIST).text(
            TextRequestDTO(user_id="tester", session_id="s", content=scenario["message"]))
        assert {c["format"].split("_response")[0]: c["model"] for c in llm.calls} == {
            "triage_specialist_phase1": "gemini-3.5-flash-lite", "project_manager_phase2": "gemini-3.8-flash",
            "safety_quality_gatekeeper_phase3": "gemini-3.1-flash-lite", "phase4_single_action": "gemini-2.5-flash",
            "phase5_single_action": "gemini-3.7-flash", "phase6_single_action": "gemini-2.5-flash-lite",
            "draft_writer_phase7": "gemini-3.6-flash", "editor_in_chief_phase8": "gemini-3.1-pro-preview"}

    def test_the_answer_checker_and_the_question_use_their_own_models(self, config):
        config({"steps": {"answer_checker": "gemini-2.5-flash-lite", "user_clarification": "gemini-3.5-flash-lite"}})
        from application.inbound.dto.session import MessageReceivedRequestDTO, StartSessionRequestDTO
        from application.service.session_service import SessionService
        from test_resume import CHECK, TRIAGE_ASKS, TRIAGE_OK, Script, _verdict
        from test_flow_golden import TRIAGE as TRIAGE_FORMAT
        llm = ScriptedLLM(overrides={TRIAGE_FORMAT: Script(TRIAGE_ASKS, TRIAGE_OK),
                                     CHECK: Script(_verdict("answered", "Ana"))})
        service = SessionService(outbound_port=llm, mcp_list=[])
        sid = service.start_session(StartSessionRequestDTO(user_id="tester", username="t")).session_id
        for text in ("Make a table", "Ana"):
            service.message_received(MessageReceivedRequestDTO(user_id="tester", session_id=sid, message=text))
        models = {c["format"].split("_response")[0]: c["model"] for c in llm.calls}
        assert models["answer_checker_phase9"] == "gemini-2.5-flash-lite"
        assert llm.calls[1]["model"] == "gemini-3.5-flash-lite"                # the question for the user (phase 99)


# ===============================================
#  THE SHIPPED FILES
# ===============================================

@pytest.fixture
def shipped(monkeypatch):
    monkeypatch.setenv(MODELS_FILE_VARIABLE, CONFIG_PATH)


class TestShippedConfig:
    def test_it_loads_and_every_id_is_in_the_catalog(self, shipped):
        config = load_config()
        assert config["profile"] in config["profiles"]
        assert set(config["profiles"]) >= {"proven", "budget", "balanced", "quality"}

    def test_the_active_profile_works_out_of_the_box(self, shipped):
        assert config_profile() in load_config()["profiles"]
        assert all(model for model, _ in effective_models().values())

    @pytest.mark.parametrize("profile", ["proven", "budget", "balanced", "quality"])
    def test_every_profile_resolves_every_step_to_a_gemini_model_of_the_table(self, shipped, tmp_path, monkeypatch, profile):
        data = json.load(open(CONFIG_PATH, encoding="utf-8"))
        data["profile"] = profile
        path = tmp_path / "p.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setenv(MODELS_FILE_VARIABLE, str(path))
        ids = {m["id"] for m in load_models()["models"]}
        resolved = effective_models()
        assert set(resolved) == set(STEP_NAMES)
        assert all(model in ids for model, _ in resolved.values()), resolved

    def test_the_steps_section_lists_every_step_and_chooses_nothing(self, shipped):
        steps = load_config()["steps"]
        assert set(steps) == set(STEP_NAMES) and all(v is None for v in steps.values())

    def test_the_provider_of_every_model_is_google(self, shipped):
        for model in load_models()["models"]:
            assert get_selected_model(model["id"]).is_google(), model["id"]


def config_profile():
    return load_config()["profile"]


class TestTheTable:
    def test_the_models_are_sorted_from_the_lowest_to_the_highest_cost(self):
        costs = [blended(m) for m in load_models()["models"]]
        assert costs == sorted(costs) and costs[0] < costs[-1]

    def test_every_model_is_in_the_catalog_once(self):
        ids = [m["id"] for m in load_models()["models"]]
        assert len(ids) == len(set(ids))
        for model_id in ids:
            assert get_selected_model(model_id).id == model_id

    def test_every_model_has_a_price_and_a_rating_for_every_step(self):
        data = load_models()
        assert list(data["steps"]) == STEP_NAMES
        for model in data["models"]:
            assert model["input"] > 0 and model["output"] > 0 and model["name"] and model["summary"]
            assert list(model["ratings"]) == STEP_NAMES, model["id"]
            for step, (level, why) in model["ratings"].items():
                assert level in LEVELS and why, (model["id"], step)

    def test_every_model_says_if_it_answered_a_test_call(self):
        for model in load_models()["models"]:
            assert model["api_check"] == "answered" or model["api_check"].startswith("FAILED"), model["id"]

    def test_a_model_that_the_api_refused_is_rated_avoid_everywhere(self):
        for model in load_models()["models"]:
            if model["api_check"].startswith("FAILED"):
                assert {level for level, _ in model["ratings"].values()} == {"avoid"}, model["id"]

    def test_the_profiles_never_use_a_model_the_api_refused(self):
        refused = {m["id"] for m in load_models()["models"] if m["api_check"].startswith("FAILED")}
        config = json.load(open(CONFIG_PATH, encoding="utf-8"))
        used = {v for p in config["profiles"].values() for k, v in p.items() if not k.startswith("_") and v}
        assert not used & refused

    def test_the_cost_of_a_message(self):
        model = {"input": 0.30, "output": 2.50}
        assert blended(model) == pytest.approx(0.85)
        assert per_message(model, 10_000) == pytest.approx(0.0085)

    def test_the_document_is_up_to_date(self):
        expected = markdown(load_models(), json.load(open(CONFIG_PATH, encoding="utf-8")))
        actual = open(DOC_PATH, encoding="utf-8").read()
        assert actual == expected, "run: windows\\Scripts\\python.exe tests\\manual\\show_models.py --write"

    def test_the_document_has_the_columns_that_were_asked_for(self):
        text = open(DOC_PATH, encoding="utf-8").read()
        header = next(line for line in text.splitlines() if line.startswith("| # | Name"))
        for column in ("Name", "Model id", "Input $/1M", "Output $/1M", "Blended $/1M", "$ per message"):
            assert column in header
        assert "`gemini-2.5-flash-lite`" in text and "`gemini-3.1-pro-preview`" in text

    def test_every_step_has_its_own_table_with_cost_and_rating(self):
        text = open(DOC_PATH, encoding="utf-8").read()
        data = load_models()
        for step in STEP_NAMES:
            section = text.split(f"### {step}\n")[1].split("\n### ")[0].split("\n## ")[0]
            header = next(line for line in section.splitlines() if line.startswith("| Model |"))
            for column in ("Model id", "Input $/1M", "Output $/1M", "$ per call", "$ per 1,000 calls", "Rating", "Why", "Use it"):
                assert column in header, (step, column)
            rows = [line for line in section.splitlines() if line.startswith("| Gemini")]
            assert len(rows) == len(data["models"]), step
            ids = [row.split("`")[1] for row in rows]
            assert ids == [m["id"] for m in data["models"]], step                 # cheapest first, same order in every table

    def test_the_use_it_column_is_the_line_to_paste_in_steps(self):
        text = open(DOC_PATH, encoding="utf-8").read()
        assert '`"project_manager": "gemini-3.8-flash"`' in text
        for step in STEP_NAMES:
            for model in load_models()["models"]:
                json.loads("{" + f'"{step}": "{model["id"]}"' + "}")

    def test_every_step_has_a_token_count_and_a_number_of_calls(self):
        data = load_models()
        assert list(data["step_tokens"]) == STEP_NAMES
        for info in data["step_tokens"].values():
            assert isinstance(info["tokens"], int) and info["tokens"] > 0 and info["calls"] and info["note"]

    def test_the_cost_of_a_call_of_a_step(self):
        model = {"input": 0.30, "output": 2.50}
        assert per_call(model, 2000) == pytest.approx(0.0017)

    def test_the_options_of_a_step(self):
        options = best_options(load_models(), "data_engineer")
        assert options["cheapest_best"]["id"] == "gemini-2.5-flash-lite"
        assert options["strongest"]["id"] == "gemini-3.1-flash-lite"
        planner = best_options(load_models(), "project_manager")
        assert planner["cheapest_best"]["id"] == "gemini-3.8-flash" and planner["cheapest_good"]["id"] == "gemini-2.5-flash"
        assert planner["strongest"]["id"] == "gemini-3.1-pro-preview"

    def test_the_summary_table_has_a_row_per_step(self):
        text = open(DOC_PATH, encoding="utf-8").read()
        summary = text.split("## 1. Choose the model of each step")[1].split("## 2.")[0]
        assert all(f"| {step} |" in summary for step in STEP_NAMES)
        assert "Cheapest rated best" in summary and "Uses now" in summary


class TestChoosingFromTheTool:
    @pytest.fixture
    def file(self, tmp_path, monkeypatch):
        path = tmp_path / "step_models.json"
        path.write_text(open(CONFIG_PATH, encoding="utf-8").read(), encoding="utf-8")
        monkeypatch.setenv(MODELS_FILE_VARIABLE, str(path))
        set_profile("proven", str(path))                    # whatever profile is active in the shipped file
        return str(path)

    def test_a_step_is_chosen_and_the_agent_uses_it(self, file):
        set_step("project_manager", "gemini-3.8-flash", file)
        assert read_config(file)["steps"]["project_manager"] == "gemini-3.8-flash"
        assert effective_models()["project_manager"] == ("gemini-3.8-flash", "config steps")
        assert effective_models()["triage_specialist"][0] == "gemini-2.5-flash"      # the others do not change

    def test_a_choice_can_be_cleared(self, file):
        set_step("project_manager", "gemini-3.8-flash", file)
        set_step("project_manager", None, file)
        assert effective_models()["project_manager"][1] == "profile proven default"

    def test_the_profile_changes_every_step(self, file):
        set_profile("budget", file)
        models = {name: model for name, (model, _) in effective_models().items()}
        assert models["triage_specialist"] == "gemini-2.5-flash-lite" and models["project_manager"] == "gemini-2.5-flash"

    def test_an_unknown_step_is_refused_and_the_file_is_not_touched(self, file):
        before = open(file, encoding="utf-8").read()
        with pytest.raises(ValueError, match="unknown step 'project_manger'"):
            set_step("project_manger", "gemini-3.8-flash", file)
        assert open(file, encoding="utf-8").read() == before

    def test_an_unknown_model_is_refused_and_the_file_is_not_touched(self, file):
        before = open(file, encoding="utf-8").read()
        with pytest.raises(ValueError, match="'gemini-9' is not a model of the catalog"):
            set_step("project_manager", "gemini-9", file)
        assert open(file, encoding="utf-8").read() == before

    def test_an_unknown_profile_is_refused_and_the_file_is_not_touched(self, file):
        before = open(file, encoding="utf-8").read()
        with pytest.raises(ValueError, match="profile 'cheapest' is not defined"):
            set_profile("cheapest", file)
        assert open(file, encoding="utf-8").read() == before

    def test_the_help_text_and_the_other_choices_are_kept(self, file):
        set_step("draft_writer", "gemini-3.6-flash", file)
        config = read_config(file)
        assert config["_help"].startswith("Which LLM answers each step") and set(config["profiles"]) >= {"budget", "quality"}
        assert config["steps"]["draft_writer"] == "gemini-3.6-flash"
