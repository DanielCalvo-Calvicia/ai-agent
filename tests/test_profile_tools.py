# T-05.17: `check_agent.py --explain <profile>`, the table of every profile (docs/models/profiles.md) and `run_profile.py`.
import importlib.util
import json
import os
import shutil
import subprocess
import sys

import pytest

from application.engine.assemble import assemble
from application.engine.config_snapshot import build_snapshot
from infrastructure.outbound.config.file_source import FileConfigSource
from infrastructure.outbound.mcp.config import SUPPORTED_TYPES, load_mcp_configs
from profile_tables import DOC_PATH, explain, explain_text, profiles_markdown, steps_of

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SERVERS = [s["name"] for s in load_mcp_configs(os.path.join(PROJECT_ROOT, "mcps")) if s["type"] in SUPPORTED_TYPES]
NAMES = ["identification", "chat", "special", "dynamics", "default", "movement", "gesture"]


def script(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(PROJECT_ROOT, "scripts", f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def agent():
    built = assemble(build_snapshot(FileConfigSource(PROJECT_ROOT)))
    built.raise_on_errors()
    return built


# ===============================================
#  --explain
# ===============================================

class TestExplain:
    def test_the_steps_of_special_in_order_with_the_executors_three_after_the_executor(self, agent):
        assert [(s, child) for s, child in steps_of(agent, "special")] == [
            ("triage_specialist", False), ("project_manager", False), ("safety_quality_gatekeeper", False), ("action_executor", False),
            ("cognitive_worker", True), ("mcp_operator", True), ("data_engineer", True), ("draft_writer", False), ("editor_in_chief", False)]

    def test_the_model_of_each_step_and_where_it_comes_from(self, agent):
        rows = {r["step"]: r for r in explain(agent, "special", SERVERS)["rows"]}
        assert rows["project_manager"]["models"] == ["claude-sonnet-5-5"] and rows["triage_specialist"]["models"] == ["claude-haiku-4-5"]
        assert rows["project_manager"]["source"] == "models (set claude_mixed)"
        assert rows["action_executor"]["models"] == [] and rows["action_executor"]["kind"] == "code"

    def test_the_proven_set_lists_the_fallback_after_the_first_model(self, agent):
        assert explain(agent, "movement", SERVERS)["rows"][0]["models"] == ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3-flash-preview"]

    def test_the_tools_of_each_profile(self, agent):
        tools = {name: {r["step"]: r["tools"] for r in explain(agent, name, SERVERS)["rows"] if r["tools"] is not None} for name in ("special", "dynamics", "default")}
        assert sorted(tools["special"]["mcp_operator"]) == ["aws_microservice", "dynamics_microservice"]
        assert tools["dynamics"] == {"project_manager": ["dynamics_microservice"], "mcp_operator": ["dynamics_microservice"]}
        assert tools["default"] == {"project_manager": [], "mcp_operator": []}

    def test_the_prompt_of_each_step_and_the_override_of_a_profile(self, agent):
        import dataclasses
        from application.engine.support.prompt_overrides import PromptOverride
        profile = agent.profile("chat")
        changed = type(agent)({**agent.profiles, "chat": dataclasses.replace(profile, prompts={"draft_writer": PromptOverride(append="x")})},
                              agent.problems, agent.flows, agent.step_defs, agent.step_prompts)
        rows = {r["step"]: r for r in explain(changed, "chat", SERVERS)["rows"]}
        assert rows["draft_writer"]["prompt"] == "prompts/7_drawf_writter.txt" and rows["draft_writer"]["prompt_override"] == "append"
        assert rows["editor_in_chief"]["prompt_override"] == ""

    def test_the_hash_is_the_one_of_the_assembled_profile(self, agent):
        assert explain(agent, "special", SERVERS)["hash"] == agent.profile("special").profile_hash

    def test_the_cost_of_a_full_plan_is_priced_from_the_catalog_and_grows_with_the_model(self, agent):
        special, default = explain(agent, "special", SERVERS), explain(agent, "default", SERVERS)
        assert special["visible"] > default["visible"] > 0 and not special["partial"]
        assert explain(agent, "chat", SERVERS)["visible"] < special["visible"]

    def test_a_step_with_no_token_estimate_has_no_cost_and_the_total_is_partial(self, agent):
        movement = explain(agent, "movement", SERVERS)
        assert movement["visible"] == 0 and movement["partial"]

    def test_the_text_has_one_line_per_step_and_the_cost(self, agent):
        text = explain_text(explain(agent, "special", SERVERS))
        for step in ("triage_specialist", "cognitive_worker", "editor_in_chief"):
            assert step in text
        assert text.startswith("profile special: flow special") and "cost of one message with a big plan" in text
        assert agent.profile("special").profile_hash in text

    def test_the_command_prints_it_and_refuses_an_unknown_profile(self):
        env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [os.environ.get("PYTHONPATH"), PROJECT_ROOT]))}
        good = subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "scripts", "check_agent.py"), "--explain", "special"],
                              capture_output=True, text=True, env=env, cwd=PROJECT_ROOT)
        assert good.returncode == 0 and "profile special: flow special" in good.stdout, good.stdout + good.stderr
        bad = subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "scripts", "check_agent.py"), "--explain", "nope"],
                             capture_output=True, text=True, env=env, cwd=PROJECT_ROOT)
        assert bad.returncode == 1 and "no profile 'nope'" in bad.stdout


# ===============================================
#  THE TABLE OF EVERY PROFILE
# ===============================================

class TestTheGeneratedTable:
    def test_one_section_per_profile(self, agent):
        text = profiles_markdown(agent, SERVERS)
        for name in NAMES:
            assert f"## `{name}`" in text
        assert text.count("**Total for one message**") == len(NAMES)

    def test_the_document_of_the_repository_is_the_generated_one(self, agent):
        with open(DOC_PATH, encoding="utf-8") as f:
            assert f.read() == profiles_markdown(agent, SERVERS), "run: python scripts/model_tables.py --profiles"

    def test_the_old_show_models_tool_is_gone_and_its_options_live_in_model_tables(self):
        assert not os.path.exists(os.path.join(PROJECT_ROOT, "tests", "manual", "show_models.py"))
        assert os.path.isfile(os.path.join(PROJECT_ROOT, "scripts", "model_tables.py"))


# ===============================================
#  run_profile.py
# ===============================================

@pytest.fixture
def root(tmp_path):
    for folder in ("profiles", "flows", "step_defs", "model_sets", "prompts", "config", "mcps"):
        shutil.copytree(os.path.join(PROJECT_ROOT, folder), tmp_path / folder, ignore=shutil.ignore_patterns("_unverified"))
    return tmp_path


class TestRunProfile:
    def test_the_fixed_set_has_the_six_messages_each_with_what_a_good_answer_contains(self):
        run = script("run_profile")
        with open(run.DEFAULT_MESSAGES, encoding="utf-8") as f:
            messages = json.load(f)["messages"]
        assert [m["id"] for m in messages] == ["greeting", "question", "plan", "movement", "dynamics", "spanish"]
        assert all(m["message"] and m["expect"] for m in messages)

    def test_each_profile_gets_the_messages_that_make_sense_for_it(self):
        run = script("run_profile")
        assert [m["id"] for m in run.messages_for("movement")] == ["greeting", "question", "movement", "spanish"]
        assert [m["id"] for m in run.messages_for("dynamics")] == ["greeting", "question", "plan", "dynamics", "spanish"]
        assert [m["id"] for m in run.messages_for("gesture")] == ["greeting", "question", "spanish"]

    def test_on_a_mock_adapter_it_writes_the_answers_and_the_note(self, root):
        run = script("run_profile")
        before = assemble(build_snapshot(FileConfigSource(str(root)))).profile("chat").profile_hash
        assert run.main(["chat", "--mock", "--root", str(root), "--date", "2026-11-04"]) == 0
        report = (root / "tests" / "output" / "profile_run_chat_2026-11-04.md").read_text(encoding="utf-8")
        assert "(a scripted model: not a real run)" in report and "## greeting" in report and "**Must contain:**" in report and "**Answer:** " in report
        assert json.loads((root / "profiles" / "chat.json").read_text(encoding="utf-8"))["tested"] == "2026-11-04"
        assert assemble(build_snapshot(FileConfigSource(str(root)))).profile("chat").profile_hash == before      # the note is not part of the hash

    def test_a_profile_that_needs_a_reply_gets_the_message_as_the_reply(self, root):
        run = script("run_profile")
        assert run.main(["gesture", "--mock", "--root", str(root), "--date", "2026-11-04"]) == 0
        assert "A gesture." in (root / "tests" / "output" / "profile_run_gesture_2026-11-04.md").read_text(encoding="utf-8")

    def test_the_other_profiles_files_are_not_touched(self, root):
        run = script("run_profile")
        before = (root / "profiles" / "special.json").read_bytes()
        run.main(["chat", "--mock", "--root", str(root), "--date", "2026-11-04"])
        assert (root / "profiles" / "special.json").read_bytes() == before

    def test_a_message_that_fails_is_reported_and_the_profile_is_not_marked(self, root, monkeypatch):
        run = script("run_profile")
        original = run.run_message

        def failing(agent, adapter, mcp_list, mcp_tools, cost_of, profile_name, message):
            if "France" in message:
                raise RuntimeError("the model is down")
            return original(agent, adapter, mcp_list, mcp_tools, cost_of, profile_name, message)

        monkeypatch.setattr(run, "run_message", failing)
        assert run.main(["chat", "--mock", "--root", str(root), "--date", "2026-11-04"]) == 1
        assert "ERROR: RuntimeError: the model is down" in (root / "tests" / "output" / "profile_run_chat_2026-11-04.md").read_text(encoding="utf-8")
        assert json.loads((root / "profiles" / "chat.json").read_text(encoding="utf-8")).get("tested") is None

    def test_a_real_run_asks_first_and_runs_nothing_without_an_answer(self, root, monkeypatch, capsys):
        run = script("run_profile")
        monkeypatch.setattr(run, "real_services", lambda *a: pytest.fail("a real adapter was built without asking"))
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        assert run.main(["chat", "--root", str(root)]) == 2
        assert "pass --yes to run without asking" in capsys.readouterr().out
        assert not (root / "tests" / "output").exists()

    def test_a_no_answers_the_question(self, root, monkeypatch, capsys):
        run = script("run_profile")
        monkeypatch.setattr(run, "real_services", lambda *a: pytest.fail("a real adapter was built after a no"))
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda prompt="": "n")
        assert run.main(["chat", "--root", str(root)]) == 2 and "Nothing was run." in capsys.readouterr().out

    def test_an_unknown_profile_is_refused(self, root, capsys):
        run = script("run_profile")
        assert run.main(["nope", "--mock", "--root", str(root)]) == 1 and "no profile 'nope'" in capsys.readouterr().out
