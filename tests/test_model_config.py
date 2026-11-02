# pyright: reportOptionalSubscript=false
"""Which LLMs answer each step: the resolver (profile, flow, step), the model sets, and the table of Gemini models."""
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.engine.config_snapshot import build_snapshot
from application.engine.support.metrics import PHASE_NAMES
from application.engine.support.model_selection import (
    ALL_STEP_NAMES, DEFAULT_MODEL_SET, STEP_NAMES, ModelResolver, check_model_set, effective_models,
)
from domain.value_objects.llm_request.model import GoogleModels, get_selected_model
from infrastructure.outbound.config.file_source import FileConfigSource
from model_table import (DOC_PATH, LEVELS, MODEL_SETS_DIR, best_options, blended, load_models, markdown, per_call,
                         per_message, read_config, read_model_sets)

from test_flow_golden import MCP_LIST, SCENARIOS, ScriptedLLM

DEFAULT = GoogleModels.GEMINI_3_6_FLASH
TRIAGE, PLANNER, GATE, WORKER, TOOLS, CLEANER, DRAFT, EDITOR, CHECKER, QUESTION = 1, 2, 3, 4, 5, 6, 7, 8, 9, 99
OLD_TABLE = os.path.join(PROJECT_ROOT, "tests", "golden", "step_models_before_T-05.5.json")     # config/step_models.json as it was on 2026-11-02
FLOW = "special"


def ids(resolver, step, flow=FLOW, default=DEFAULT):
    return [m.id for m in resolver.models_for(flow, step, default)]


# ===============================================
#  THE CODE DEFAULTS
# ===============================================

class TestCodeDefaults:
    def test_every_phase_falls_back_to_a_google_model_with_a_free_tier(self):
        from application.steps.catalog import PHASES
        free = {m["id"] for m in load_models()["models"] if m["free_tier"]}
        assert PHASES
        for phase_id, info in PHASES.items():
            if info.default_model is not None:
                assert get_selected_model(info.default_model).is_google(), phase_id
                assert info.default_model.value in free, phase_id

    def test_the_small_steps_use_the_lite_model_and_the_others_the_flash_model(self):
        from application.steps.catalog import PHASES
        small = {"triage_specialist", "data_engineer", "answer_checker", "user_clarification", "emotion_reader"}
        for info in PHASES.values():
            if info.default_model is not None:
                expected = "gemini-3.1-flash-lite" if info.step_name in small else "gemini-3.6-flash"
                assert info.default_model.value == expected, info.step_name


# ===============================================
#  ORDER OF PRECEDENCE: the most specific value replaces the broader one
# ===============================================

SETS = {
    "cheap": {"default": ["gemini-3.1-flash-lite"], "project_manager": ["gemini-3.8-flash"]},
    "safe": {"default": ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3-flash-preview"]},
}


class TestResolver:
    def test_without_a_profile_every_step_uses_its_own_default(self):
        resolver = ModelResolver()
        assert ids(resolver, "project_manager") == ["gemini-3.6-flash"]
        assert ids(resolver, "triage_specialist", default=GoogleModels.GEMINI_3_1_FLASH_LITE) == ["gemini-3.1-flash-lite"]
        assert resolver.source_for(FLOW, "project_manager") == "step default"

    def test_a_list_of_the_profile_covers_every_step_and_the_rest_of_it_is_the_fallback(self):
        resolver = ModelResolver({"models": ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]})
        for step in (TRIAGE, PLANNER, CHECKER, QUESTION):
            assert ids(resolver, PHASE_NAMES[step]) == ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]

    def test_a_model_set_gives_its_entry_of_the_step_and_its_default_to_the_others(self):
        resolver = ModelResolver({"models": "cheap"}, SETS)
        assert ids(resolver, "project_manager") == ["gemini-3.8-flash"]
        assert ids(resolver, "safety_quality_gatekeeper") == ["gemini-3.1-flash-lite"]
        assert resolver.source_for(FLOW, "project_manager") == "models (set cheap)"

    def test_the_models_of_a_flow_beat_the_models_of_the_profile_in_that_flow_only(self):
        resolver = ModelResolver({"models": ["gemini-3.1-flash-lite"], "flows": {"chat": {"models": ["gemini-3.8-flash"]}}})
        assert ids(resolver, "draft_writer", flow="chat") == ["gemini-3.8-flash"]
        assert ids(resolver, "draft_writer", flow="special") == ["gemini-3.1-flash-lite"]

    def test_the_same_step_can_have_two_models_in_two_flows(self):
        resolver = ModelResolver({"models": ["gemini-3.1-flash-lite"],
                                  "flows": {"chat": {"steps": {"draft_writer": {"models": ["gemini-3.5-flash-lite"]}}},
                                            "special": {"steps": {"draft_writer": {"models": ["gemini-3.8-flash"]}}}}})
        assert ids(resolver, "draft_writer", flow="chat") == ["gemini-3.5-flash-lite"]
        assert ids(resolver, "draft_writer", flow="special") == ["gemini-3.8-flash"]
        assert ids(resolver, "editor_in_chief", flow="special") == ["gemini-3.1-flash-lite"]

    def test_an_override_of_a_step_beats_the_flow_and_the_profile_in_every_flow(self):
        resolver = ModelResolver({"models": ["gemini-3.1-flash-lite"], "flows": {"chat": {"models": ["gemini-3.8-flash"]}},
                                  "overrides": {"draft_writer": {"models": ["gemini-3.1-pro-preview"]}}})
        assert ids(resolver, "draft_writer", flow="chat") == ["gemini-3.1-pro-preview"]
        assert ids(resolver, "draft_writer", flow="special") == ["gemini-3.1-pro-preview"]
        assert ids(resolver, "editor_in_chief", flow="chat") == ["gemini-3.8-flash"]

    def test_a_step_of_a_flow_beats_an_override_of_the_step(self):
        resolver = ModelResolver({"overrides": {"draft_writer": {"models": ["gemini-3.1-pro-preview"]}},
                                  "flows": {"chat": {"steps": {"draft_writer": {"models": ["gemini-3.5-flash-lite"]}}}}})
        assert ids(resolver, "draft_writer", flow="chat") == ["gemini-3.5-flash-lite"]
        assert ids(resolver, "draft_writer", flow="special") == ["gemini-3.1-pro-preview"]

    def test_a_model_set_may_be_named_at_any_level(self):
        resolver = ModelResolver({"models": ["gemini-3.1-flash-lite"], "flows": {"chat": {"models": "cheap"}},
                                  "overrides": {"editor_in_chief": {"models": "safe"}}}, SETS)
        assert ids(resolver, "project_manager", flow="chat") == ["gemini-3.8-flash"]
        assert ids(resolver, "editor_in_chief", flow="chat") == ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3-flash-preview"]
        assert resolver.source_for("chat", "editor_in_chief") == "overrides.editor_in_chief (set safe)"

    def test_the_whole_list_is_replaced_never_added_to(self):
        resolver = ModelResolver({"models": "safe", "overrides": {"project_manager": {"models": ["gemini-3.8-flash"]}}}, SETS)
        assert ids(resolver, "project_manager") == ["gemini-3.8-flash"]                   # the fallbacks of the set do not come along
        assert len(ids(resolver, "draft_writer")) == 3

    def test_a_level_that_says_nothing_about_the_step_lets_the_next_one_decide(self):
        sets = {"only_planner": {"project_manager": ["gemini-3.8-flash"]}}                # no `default`
        resolver = ModelResolver({"models": ["gemini-3.1-flash-lite"], "flows": {"chat": {"models": "only_planner"}}}, sets)
        assert ids(resolver, "draft_writer", flow="chat") == ["gemini-3.1-flash-lite"]
        assert ids(resolver, "project_manager", flow="chat") == ["gemini-3.8-flash"]

    def test_a_level_set_to_null_is_skipped(self):
        resolver = ModelResolver({"models": ["gemini-3.6-flash"], "overrides": {"project_manager": {"models": None}}})
        assert ids(resolver, "project_manager") == ["gemini-3.6-flash"]

    def test_each_name_of_a_step_is_its_phase(self):
        models = ("gemini-3.6-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite")      # three different ids, repeated
        names = {name: models[i % 3] for i, name in enumerate(STEP_NAMES)}
        resolver = ModelResolver({"overrides": {name: {"models": [model]} for name, model in names.items()}})
        for phase, name in PHASE_NAMES.items():
            assert ids(resolver, name) == [names[name]], name

    def test_a_model_of_another_provider_can_be_used(self):
        model = ModelResolver({"models": ["llama-3.3-70b-versatile"]}).models_for(FLOW, "project_manager", DEFAULT)[0]
        assert model.id == "llama-3.3-70b-versatile" and model.is_groq()

    def test_the_source_of_each_choice_is_reported(self):
        resolver = ModelResolver({"models": "cheap", "overrides": {"draft_writer": {"models": ["gemini-3.1-flash-lite"]}}}, SETS)
        sources = {name: source for name, (_, source) in effective_models(resolver).items()}
        assert sources["draft_writer"] == "overrides.draft_writer"
        assert sources["triage_specialist"] == "models (set cheap)"
        assert effective_models(ModelResolver())["project_manager"][1] == "step default"


class TestMistakes:
    def test_an_unknown_step_lists_the_valid_ones(self):
        with pytest.raises(ValueError, match="unknown step 'project_manger'.*triage_specialist"):
            ModelResolver({"overrides": {"project_manger": {"models": ["gemini-3.6-flash"]}}})            # a typo

    def test_an_unknown_step_of_a_flow(self):
        with pytest.raises(ValueError, match="flows.chat.steps: unknown step 'writer'"):
            ModelResolver({"flows": {"chat": {"steps": {"writer": {"models": ["gemini-3.6-flash"]}}}}})

    def test_an_unknown_model_names_the_place_of_the_mistake(self):
        with pytest.raises(ValueError, match="profile overrides.project_manager.models: 'gemini-9-ultra' is not a model of the catalog"):
            ModelResolver({"overrides": {"project_manager": {"models": ["gemini-9-ultra"]}}})

    def test_an_unknown_model_set_lists_the_ones_that_exist(self):
        with pytest.raises(ValueError, match="profile models: unknown model set 'nope'. Model sets: cheap, safe"):
            ModelResolver({"models": "nope"}, SETS)

    def test_a_list_must_not_be_empty_and_must_be_a_list(self):
        with pytest.raises(ValueError, match="must be a list of model ids"):
            ModelResolver({"models": []})
        with pytest.raises(ValueError, match="unknown model set 'gemini-3.6-flash'"):
            ModelResolver({"flows": {"chat": {"models": "gemini-3.6-flash"}}}, {})                        # a string is a set name, and none exists
        with pytest.raises(ValueError, match="must be a list of model ids"):
            ModelResolver({"models": {"default": ["gemini-3.6-flash"]}})                                   # a table is not a list

    def test_a_model_set_with_an_unknown_step_or_model_is_refused(self):
        with pytest.raises(ValueError, match="model_sets/bad.json: unknown step 'project_manger'"):
            check_model_set("bad", {"project_manger": ["gemini-3.6-flash"]})
        with pytest.raises(ValueError, match="model_sets/bad.json: default: 'nope'"):
            check_model_set("bad", {"default": ["nope"]})
        with pytest.raises(ValueError, match="needs `default` or at least one step"):
            check_model_set("bad", {"schema_version": 1, "name": "bad", "_about": "no entries"})

    def test_a_set_that_is_used_is_checked_when_the_resolver_is_built(self):
        with pytest.raises(ValueError, match="model_sets/bad.json"):
            ModelResolver({"models": "bad"}, {"bad": {"default": ["nope"]}})

    def test_keys_that_start_with_an_underscore_are_ignored_in_a_set(self):
        check_model_set("ok", {"schema_version": 1, "name": "ok", "_about": "text", "_note": 3, "default": ["gemini-3.6-flash"]})


# ===============================================
#  THE CHOICE REACHES THE LLM CALLS
# ===============================================

class TestReachesTheCalls:
    def test_every_step_calls_the_model_of_its_profile(self):
        models = {"triage_specialist": "gemini-3.5-flash-lite", "project_manager": "gemini-3.8-flash",
                  "safety_quality_gatekeeper": "gemini-3.1-flash-lite", "cognitive_worker": "gemini-3.6-flash",
                  "mcp_operator": "gemini-3-flash-preview", "data_engineer": "gemini-3.1-flash-lite",
                  "draft_writer": "gemini-3.6-flash", "editor_in_chief": "gemini-3.1-pro-preview"}
        resolver = ModelResolver({"overrides": {step: {"models": [model]} for step, model in models.items()}})
        scenario = SCENARIOS["full_path_with_mcp"]
        llm = ScriptedLLM(**scenario["llm"])
        from application.service.message_flow_service import MessageFlowService
        from application.inbound.dto.message import TextRequestDTO
        MessageFlowService(outbound_port=llm, mcp_list=MCP_LIST, models=resolver).text(
            TextRequestDTO(user_id="tester", session_id="s", content=scenario["message"]))
        assert {c["format"].split("_response")[0]: c["model"] for c in llm.calls} == {
            "triage_specialist_phase1": "gemini-3.5-flash-lite", "project_manager_phase2": "gemini-3.8-flash",
            "safety_quality_gatekeeper_phase3": "gemini-3.1-flash-lite", "phase4_single_action": "gemini-3.6-flash",
            "phase5_single_action": "gemini-3-flash-preview", "phase6_single_action": "gemini-3.1-flash-lite",
            "draft_writer_phase7": "gemini-3.6-flash", "editor_in_chief_phase8": "gemini-3.1-pro-preview"}

    def test_the_same_step_uses_the_model_of_its_flow(self):
        resolver = ModelResolver({"models": ["gemini-3.1-flash-lite"], "flows": {"special": {"steps": {
            "editor_in_chief": {"models": ["gemini-3.8-flash"]}}}}})
        scenario = SCENARIOS["full_path_with_mcp"]
        llm = ScriptedLLM(**scenario["llm"])
        from application.service.message_flow_service import MessageFlowService
        from application.inbound.dto.message import TextRequestDTO
        MessageFlowService(outbound_port=llm, mcp_list=MCP_LIST, models=resolver).text(
            TextRequestDTO(user_id="tester", session_id="s", content=scenario["message"]))
        models = {c["format"].split("_response")[0]: c["model"] for c in llm.calls}
        assert models["editor_in_chief_phase8"] == "gemini-3.8-flash"
        assert models["draft_writer_phase7"] == "gemini-3.1-flash-lite"

    def test_the_answer_checker_and_the_question_use_their_own_models(self):
        resolver = ModelResolver({"overrides": {"answer_checker": {"models": ["gemini-3.1-flash-lite"]},
                                                "user_clarification": {"models": ["gemini-3.5-flash-lite"]}}})
        from application.inbound.dto.session import MessageReceivedRequestDTO, StartSessionRequestDTO
        from application.service.session_service import SessionService
        from test_resume import CHECK, TRIAGE_ASKS, TRIAGE_OK, Script, _verdict
        from test_flow_golden import TRIAGE as TRIAGE_FORMAT
        llm = ScriptedLLM(overrides={TRIAGE_FORMAT: Script(TRIAGE_ASKS, TRIAGE_OK),
                                     CHECK: Script(_verdict("answered", "Ana"))})
        service = SessionService(outbound_port=llm, mcp_list=[], models=resolver)
        sid = service.start_session(StartSessionRequestDTO(user_id="tester", username="t")).session_id
        for text in ("Make a table", "Ana"):
            service.message_received(MessageReceivedRequestDTO(user_id="tester", session_id=sid, message=text))
        models = {c["format"].split("_response")[0]: c["model"] for c in llm.calls}
        assert models["answer_checker_phase9"] == "gemini-3.1-flash-lite"
        assert llm.calls[1]["model"] == "gemini-3.5-flash-lite"                # the question for the user (phase 99)

    def test_without_a_resolver_the_defaults_of_the_code_are_used(self):
        scenario = SCENARIOS["full_path_with_mcp"]
        llm = ScriptedLLM(**scenario["llm"])
        from application.service.message_flow_service import MessageFlowService
        from application.inbound.dto.message import TextRequestDTO
        MessageFlowService(outbound_port=llm, mcp_list=MCP_LIST).text(
            TextRequestDTO(user_id="tester", session_id="s", content=scenario["message"]))
        assert {c["model"] for c in llm.calls} <= {"gemini-3.1-flash-lite", "gemini-3.6-flash"}


# ===============================================
#  THE SHIPPED MODEL SETS
# ===============================================

@pytest.fixture(scope="module")
def shipped():
    return read_model_sets()


def shipped_resolver(name, flow=""):
    return ModelResolver({"models": name}, read_model_sets())


class TestShippedModelSets:
    def test_every_file_loads_and_is_right(self, shipped):
        snapshot = build_snapshot(FileConfigSource(PROJECT_ROOT))
        assert snapshot.errors == {}
        assert set(snapshot.model_sets) == set(shipped) >= {"proven", "budget", "balanced", "quality", "budget50", "claude_sonnet",
                                                           "budget50_groq", "google_free", "claude_haiku", "claude_mixed"}
        for name, data in snapshot.model_sets.items():
            check_model_set(name, data)

    def test_the_set_the_service_runs_on_exists_and_works_out_of_the_box(self, shipped):
        assert DEFAULT_MODEL_SET in shipped
        assert all(model for model, _ in effective_models(shipped_resolver(DEFAULT_MODEL_SET)).values())

    def test_proven_is_every_step_on_the_free_tier_lite_model_with_the_fallbacks_of_adr_014(self, shipped):
        assert DEFAULT_MODEL_SET == "proven"
        free = {m["id"] for m in load_models()["models"] if m["free_tier"]}
        resolver = shipped_resolver("proven")
        for step in ALL_STEP_NAMES:
            assert ids(resolver, step) == ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3-flash-preview"], step
        resolved = effective_models(resolver)
        assert {model for model, _ in resolved.values()} == {"gemini-3.1-flash-lite"} and "gemini-3.1-flash-lite" in free
        assert {source for _, source in resolved.values()} == {"models (set proven)"}

    def test_google_free_is_defined_with_the_two_free_tier_models(self, shipped):
        data = shipped["google_free"]
        used = {ids_[0] for key, ids_ in data.items() if not key.startswith("_") and key not in ("schema_version", "name")}
        free = {m["id"] for m in load_models()["models"] if m["free_tier"]}
        assert used == {"gemini-3.1-flash-lite", "gemini-3.6-flash"} and used <= free
        assert all(get_selected_model(model).is_google() for model in used)
        assert data["project_manager"][0] == "gemini-3.6-flash" and data["default"][0] == "gemini-3.1-flash-lite"

    def test_claude_mixed_puts_sonnet_on_the_planner_the_writer_and_the_editor(self, shipped):
        entries = {k: v for k, v in shipped["claude_mixed"].items() if not k.startswith("_") and k not in ("schema_version", "name")}
        assert entries == {
            "default": ["claude-haiku-4-5"],
            "project_manager": ["claude-sonnet-5-5"],
            "draft_writer": ["claude-sonnet-5-5"],
            "editor_in_chief": ["claude-sonnet-5-5"],
        }
        assert all(get_selected_model(model[0]).is_anthropic() for model in entries.values())
        assert DEFAULT_MODEL_SET != "claude_mixed"

    @pytest.mark.parametrize("name", ["claude_sonnet", "claude_haiku", "claude_mixed"])
    def test_a_claude_set_has_no_fallback_so_customer_data_stays_with_one_provider(self, shipped, name):
        for key, models in shipped[name].items():
            if not key.startswith("_") and key not in ("schema_version", "name"):
                assert len(models) == 1, (name, key)

    @pytest.mark.parametrize("name", ["proven", "budget", "balanced", "quality"])
    def test_every_gemini_set_resolves_every_step_to_a_gemini_model_of_the_table(self, name):
        table = {m["id"] for m in load_models()["models"]}
        resolved = effective_models(shipped_resolver(name))
        assert set(resolved) == set(STEP_NAMES)
        assert all(model in table for model, _ in resolved.values()), resolved

    def test_the_provider_of_every_model_of_the_table_is_google(self):
        for model in load_models()["models"]:
            assert get_selected_model(model["id"]).is_google(), model["id"]


class TestSameModelsAsBefore:
    """T-05.5 moved the ten profiles of config/step_models.json into model sets: nothing may choose another model."""

    @pytest.fixture(scope="class")
    def old(self):
        with open(OLD_TABLE, encoding="utf-8") as f:
            return json.load(f)["profiles"]

    def test_the_ten_profiles_are_the_ten_sets(self, old, shipped):
        assert set(old) == set(shipped) and len(old) == 10

    @pytest.mark.parametrize("name", ["proven", "budget", "balanced", "quality", "budget50", "claude_sonnet", "budget50_groq",
                                      "google_free", "claude_haiku", "claude_mixed"])
    def test_every_step_gets_the_model_and_the_fallbacks_it_got_before(self, old, name):
        profile = old[name]
        fallback = profile.get("fallback_models", [])
        resolver = shipped_resolver(name)
        for step in ALL_STEP_NAMES:
            chosen = profile.get(step) or profile["default"]
            assert ids(resolver, step) == [chosen] + [m for m in fallback if m != chosen], (name, step)


# ===============================================
#  THE TABLE OF GEMINI MODELS
# ===============================================

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
            assert model["api_check"] == "answered" or model["api_check"].startswith(("FAILED", "not called")), model["id"]

    def test_a_model_that_the_api_refused_is_rated_avoid_everywhere(self):
        for model in load_models()["models"]:
            if model["api_check"].startswith("FAILED"):
                assert {level for level, _ in model["ratings"].values()} == {"avoid"}, model["id"]

    def test_the_profiles_never_use_a_model_the_api_refused(self):
        refused = {m["id"] for m in load_models()["models"] if m["api_check"].startswith("FAILED")}
        used = {model for data in read_model_sets().values() for key, ids in data.items()
                if not key.startswith("_") and key not in ("schema_version", "name") for model in ids}   # the fallbacks are models in use too
        assert not used & refused

    def test_the_cost_of_a_message(self):
        model = {"input": 0.30, "output": 2.50}
        assert blended(model) == pytest.approx(0.85)
        assert per_message(model, 10_000) == pytest.approx(0.0085)

    def test_the_document_is_up_to_date(self):
        expected = markdown(load_models(), read_config())
        actual = open(DOC_PATH, encoding="utf-8").read()
        assert actual == expected, "run: windows\\Scripts\\python.exe tests\\manual\\show_models.py --write"

    def test_the_document_has_the_columns_that_were_asked_for(self):
        text = open(DOC_PATH, encoding="utf-8").read()
        header = next(line for line in text.splitlines() if line.startswith("| # | Name"))
        for column in ("Name", "Model id", "Input $/1M", "Output $/1M", "Blended $/1M", "$ per message"):
            assert column in header
        assert "`gemini-3.1-flash-lite`" in text and "`gemini-3.1-pro-preview`" in text

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

    def test_the_use_it_column_is_the_line_to_paste_in_a_model_set(self):
        text = open(DOC_PATH, encoding="utf-8").read()
        assert '`"project_manager": ["gemini-3.8-flash"]`' in text
        for step in STEP_NAMES:
            for model in load_models()["models"]:
                json.loads("{" + f'"{step}": ["{model["id"]}"]' + "}")

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
        assert options["cheapest_best"]["id"] == "gemini-3.1-flash-lite"
        assert options["strongest"]["id"] == "gemini-3.1-flash-lite"
        planner = best_options(load_models(), "project_manager")
        assert planner["cheapest_best"]["id"] == "gemini-3.8-flash" and planner["cheapest_good"]["id"] == "gemini-3.6-flash"
        assert planner["strongest"]["id"] == "gemini-3.1-pro-preview"

    def test_the_summary_table_has_a_row_per_step(self):
        text = open(DOC_PATH, encoding="utf-8").read()
        summary = text.split("## 1. Choose the model of each step")[1].split("## 2.")[0]
        assert all(f"| {step} |" in summary for step in STEP_NAMES)
        assert "Cheapest rated best" in summary and "Uses now" in summary
