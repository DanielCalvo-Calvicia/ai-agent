# T-05.15: one record per LLM call with profile, flow, step, model, client, tokens and cost; the hash of the assembled profile in the
# log and in Langfuse; the data fields are reserved and nothing enforces them.
import dataclasses
import json
import os
import re
import shutil

import pytest

from application.assembly.assemble import assemble
from application.assembly.config_snapshot import build_snapshot
from application.support.metrics import RECORD_KEYS, SessionMetrics
from application.inbound.dto.message import TextRequestDTO
from application.outbound.ports.usage_ports import CallDetails
from application.service.message_flow_service import MessageFlowService
from infrastructure.outbound.config.file_source import FileConfigSource
from infrastructure.outbound.usage.langfuse import LangfuseUsageReporter
from infrastructure.outbound.usage.prices import load_prices
from test_flow_golden import SCENARIOS, ScriptedLLM

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SECRET_INPUT = "SECRET-INPUT-VALUE"


def cost_of(model, prompt, completion, total):
    return {"claude-haiku-4-5": 0.001, "claude-sonnet-5-5": 0.01}.get(model)


@pytest.fixture(scope="module")
def agent():
    built = assemble(build_snapshot(FileConfigSource(PROJECT_ROOT)))
    built.raise_on_errors()
    return built


class Recorder:
    """Stands in for the module logger and keeps what was logged."""

    def __init__(self):
        self.records = []

    def info(self, message, **fields):
        self.records.append((message, fields))

    warning = info


def run_special(agent, client="web-chat", reporter=None, message=None):
    scenario = SCENARIOS["no_actions"]
    service = MessageFlowService(outbound_port=ScriptedLLM(**scenario["llm"]), mcp_list=[], agent=agent, profile="special",
                                 client=client, cost_of=cost_of, usage_reporter=reporter)
    service.text(TextRequestDTO(user_id="tester", session_id="s", content=message or scenario["message"]))
    return service.metrics


# ===============================================
#  THE RECORDS
# ===============================================

class TestEveryKeyIsInTheMetrics:
    def test_each_call_carries_profile_flow_step_model_client_hash_and_cost(self, agent):
        metrics = run_special(agent)
        assert [r.phase_name for r in metrics.request_log] == [
            "triage_specialist", "project_manager", "safety_quality_gatekeeper", "draft_writer", "editor_in_chief"]
        for record in metrics.request_log:
            assert (record.profile, record.flow, record.client) == ("special", "special", "web-chat")
            assert re.fullmatch(r"[0-9a-f]{64}", record.profile_hash) and record.profile_hash == agent.profile("special").profile_hash
            assert record.model in ("claude-haiku-4-5", "claude-sonnet-5-5") and record.cost_usd == cost_of(record.model, 0, 0, 0)
            assert record.phase_id and record.total_tokens

    def test_the_legacy_phase_id_stays_next_to_the_step_name(self, agent):
        as_dict = run_special(agent).request_log[0].to_dict()
        assert as_dict["step"] == "triage_specialist" and as_dict["phase_name"] == "triage_specialist" and as_dict["phase_id"] == 1

    def test_the_totals_by_any_key_come_from_the_records(self, agent):
        metrics = run_special(agent)
        by_model = metrics.total_by("model")
        assert sum(count.requests for count in by_model.values()) == len(metrics.request_log)
        assert set(metrics.total_by("profile")) == {("special",)} and set(metrics.total_by("client")) == {("web-chat",)}
        assert set(metrics.total_by("flow", "step")) >= {("special", "triage_specialist"), ("special", "editor_in_chief")}
        assert sum(c.total for c in metrics.total_by("profile", "flow", "step", "model", "client").values()) == metrics.totals.total
        for key in RECORD_KEYS:
            metrics.total_by(key)

    def test_a_key_that_does_not_exist_is_refused(self):
        with pytest.raises(ValueError, match="cannot total by 'token'"):
            SessionMetrics().total_by("token")

    def test_the_cost_of_the_message_is_the_sum_of_its_calls(self, agent):
        metrics = run_special(agent)
        assert metrics.message_cost() == pytest.approx(sum(r.cost_usd for r in metrics.request_log))
        assert metrics.summary()["total_cost_usd"] == metrics.message_cost()

    def test_without_prices_there_is_no_cost_and_nothing_fails(self, agent):
        scenario = SCENARIOS["no_actions"]
        service = MessageFlowService(outbound_port=ScriptedLLM(**scenario["llm"]), mcp_list=[], agent=agent, profile="special")
        service.text(TextRequestDTO(user_id="tester", session_id="s", content=scenario["message"]))
        assert service.metrics.message_cost() is None and all(r.client == "" for r in service.metrics.request_log)

    def test_a_message_with_no_assembled_profile_has_empty_run_fields(self):
        metrics = SessionMetrics()
        metrics.begin_message("t", "s", "hello")
        metrics.record(1, "m", 1, 1, 2)
        assert (metrics.request_log[0].profile, metrics.request_log[0].profile_hash) == ("", "")


class TestTheLogLine:
    def test_one_line_per_call_with_the_run_and_never_a_text_or_a_token(self, agent, monkeypatch):
        recorder = Recorder()
        monkeypatch.setattr("application.support.metrics.logger", recorder)
        metrics = run_special(agent)
        calls = [fields for message, fields in recorder.records if message == "LLM call"]
        assert len(calls) == len(metrics.request_log)
        assert set(calls[0]) == {"profile", "flow", "step", "phase_id", "model", "client", "profile_hash", "prompt_tokens",
                                 "completion_tokens", "total_tokens", "cost_usd"}
        assert calls[0]["profile_hash"] == agent.profile("special").profile_hash[:12]
        assert "token" not in " ".join(calls[0]).replace("_tokens", "").replace("tokens", "")

    def test_no_input_value_reaches_a_record_or_the_log(self, agent, monkeypatch):
        recorder = Recorder()
        monkeypatch.setattr("application.support.metrics.logger", recorder)
        metrics = run_special(agent, client="web-chat", message=f"my code is {SECRET_INPUT}")
        assert SECRET_INPUT not in json.dumps(metrics.summary(), default=str) and SECRET_INPUT not in repr(recorder.records)


# ===============================================
#  THE HASH
# ===============================================

@pytest.fixture
def config(tmp_path):
    for folder in ("profiles", "flows", "step_defs", "model_sets", "prompts"):
        shutil.copytree(os.path.join(PROJECT_ROOT, folder), tmp_path / folder, ignore=shutil.ignore_patterns("_unverified"))
    os.makedirs(tmp_path / "config")
    shutil.copy(os.path.join(PROJECT_ROOT, "config", "state_fields.json"), tmp_path / "config" / "state_fields.json")
    return tmp_path


def hash_of(config, name="special", **changes):
    path = config / "profiles" / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(changes)
    path.write_text(json.dumps(data), encoding="utf-8")
    built = assemble(build_snapshot(FileConfigSource(str(config))))
    built.raise_on_errors()
    return built.profile(name).profile_hash


class TestTheProfileHash:
    def test_it_is_a_sha256_and_the_same_every_time(self, config):
        assert hash_of(config) == hash_of(config) and re.fullmatch(r"[0-9a-f]{64}", hash_of(config))

    def test_it_changes_when_a_model_of_the_profile_changes(self, config):
        assert hash_of(config, models="claude_mixed") != hash_of(config, models="claude_haiku")

    def test_it_changes_when_the_model_set_it_names_changes(self, config):
        before = hash_of(config)
        path = config / "model_sets" / "claude_mixed.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["draft_writer"] = ["claude-haiku-4-5"]
        path.write_text(json.dumps(data), encoding="utf-8")
        assert hash_of(config) != before

    def test_it_does_not_change_when_the_token_hash_changes(self, config):
        assert hash_of(config, token_sha256="1" * 64) == hash_of(config, token_sha256="2" * 64)

    def test_it_changes_when_the_flow_file_or_a_tool_or_a_prompt_changes(self, config):
        before = hash_of(config)
        assert hash_of(config, tools={"servers": []}) != before
        assert hash_of(config, overrides={"draft_writer": {"prompt_append": {"text": "x"}}}) != hash_of(config, overrides={})
        path = config / "flows" / "special.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["about"] = "changed"
        path.write_text(json.dumps(data), encoding="utf-8")
        assert hash_of(config, tools=None) != before

    def test_two_profiles_have_two_hashes(self, agent):
        assert agent.profile("special").profile_hash != agent.profile("dynamics").profile_hash


# ===============================================
#  LANGFUSE
# ===============================================

class TestLangfuse:
    def spans(self, agent):
        reporter = LangfuseUsageReporter("pk", "sk", prices=load_prices(), background=False)
        metrics = run_special(agent, reporter=reporter)
        payloads = []
        while not reporter.queue.empty():
            payloads.append(reporter.queue.get_nowait())
        return metrics, [span for p in payloads for rs in p["resourceSpans"] for ss in rs["scopeSpans"] for span in ss["spans"]]

    @staticmethod
    def attributes(span):
        return {a["key"]: a["value"] for a in span["attributes"]}

    def test_the_trace_carries_the_tags_and_every_generation_the_metadata(self, agent):
        metrics, spans = self.spans(agent)
        root = next(s for s in spans if "parentSpanId" not in s)
        tags = [v["stringValue"] for v in self.attributes(root)["langfuse.trace.tags"]["arrayValue"]["values"]]
        assert tags == ["profile:special", "flow:special", "client:web-chat", f"hash:{agent.profile('special').profile_hash[:12]}"]
        generations = [s for s in spans if self.attributes(s).get("langfuse.observation.type", {}).get("stringValue") == "generation"]
        assert len(generations) == len(metrics.request_log)
        meta = {k: v["stringValue"] for k, v in self.attributes(generations[0]).items() if k.startswith("langfuse.observation.metadata.")}
        assert meta["langfuse.observation.metadata.profile"] == "special" and meta["langfuse.observation.metadata.flow"] == "special"
        assert meta["langfuse.observation.metadata.step"] == "triage_specialist" and meta["langfuse.observation.metadata.client"] == "web-chat"
        assert meta["langfuse.observation.metadata.profile_hash"] == agent.profile("special").profile_hash

    def test_a_message_with_no_profile_has_no_tags(self):
        reporter = LangfuseUsageReporter("pk", "sk", prices={}, background=False)
        record = SessionMetrics(reporter)
        record.begin_message("t", "s", "hi")
        record.record(1, "m", 1, 1, 2)
        spans = [s for p in [reporter.queue.get_nowait()] for rs in p["resourceSpans"] for ss in rs["scopeSpans"] for s in ss["spans"]]
        assert not any("langfuse.trace.tags" in self.attributes(s) for s in spans)


# ===============================================
#  THE RESERVED DATA FIELDS
# ===============================================

class TestTheDataFieldsAreReservedAndNothingEnforcesThem:
    def test_no_code_reads_data_allowed(self):
        hits = []
        for folder in ("application", "infrastructure", "domain", "composition_root"):
            for base, dirs, files in os.walk(os.path.join(PROJECT_ROOT, folder)):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for name in files:
                    if name.endswith(".py") and "data_allowed" in open(os.path.join(base, name), encoding="utf-8").read():
                        hits.append(name)
        assert hits == []

    def test_a_model_entry_with_data_allowed_is_priced_and_chosen_exactly_the_same(self, tmp_path):
        entry = {"id": "m-1", "input": 1.0, "output": 2.0}
        for with_field in (False, True):
            folder = tmp_path / str(with_field)
            os.makedirs(folder)
            (folder / "gemini_models.json").write_text(json.dumps({"models": [{**entry, **({"data_allowed": []} if with_field else {})}]}), encoding="utf-8")
        assert load_prices(str(tmp_path / "True")) == load_prices(str(tmp_path / "False")) == {"m-1": (1.0, 2.0)}

    def test_the_catalogs_of_the_repository_say_the_field_is_reserved(self):
        for name in ("gemini_models.json", "other_models.json"):
            with open(os.path.join(PROJECT_ROOT, "config", name), encoding="utf-8") as f:
                assert "RESERVED" in json.load(f)["_data_allowed"]

    def test_a_step_declaration_may_carry_data_reads_and_it_changes_nothing(self, config):
        from test_assemble import FakeSource, step, FIELDS
        base = {"asker": step(["message"], ["user_goal", "task_category"]), "draft": step(["user_goal", "message"], ["user_goal"])}
        with_data = {**base, "draft": {**base["draft"], "data": {"reads": ["private"]}}}
        flow = {"schema_version": 1, "steps": [{"step": "asker"}, {"step": "draft"}], "result_from": "draft"}
        profile = {"schema_version": 1, "token_sha256": "a" * 64, "flow": "chat"}
        built = [assemble(build_snapshot(FakeSource(step_defs=steps, flows={"chat": flow}, profiles={"p": profile}))) for steps in (base, with_data)]
        assert built[0].problems == built[1].problems == {}
        assert built[0].profile("p").profile_hash == built[1].profile("p").profile_hash
        assert built[0].profile("p").steps == built[1].profile("p").steps

    @pytest.mark.parametrize("value", ["private", {"writes": []}, {"reads": "private"}, {"reads": [1]}])
    def test_the_shape_of_data_is_checked_and_nothing_more(self, value):
        from test_assemble import FakeSource, step
        built = assemble(build_snapshot(FakeSource(step_defs={"s": {**step(["message"], ["user_goal"]), "data": value}})))
        assert "reserved for the data policy" in built.problems["step_defs/s"][0]
