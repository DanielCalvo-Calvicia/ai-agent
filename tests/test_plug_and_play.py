# T-05.10: adding a profile is ONE file. A temporary folder gets a copy of the configuration and one new profile file; the agent assembles and
# answers on a scripted LLM, and nothing of the repository changed. (T-05.16 adds the same for a step.)
import hashlib
import json
import os
import shutil

import pytest

from application.engine.assemble import assemble
from application.engine.config_snapshot import build_snapshot
from application.engine.profile_access import sha256_hex
from application.engine.profile_inputs import read_inputs
from application.engine.state.response_json import response_to_json
from application.inbound.dto.session import MessageReceivedRequestDTO, StartSessionRequestDTO
from application.service.message_flow_service import MessageFlowService
from application.inbound.dto.message import TextRequestDTO
from application.service.session_service import SessionService
from infrastructure.outbound.config.file_source import FileConfigSource
from infrastructure.outbound.llm.response_mapper import read_response_json
from test_flow_golden import SCENARIOS, ScriptedLLM

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
WATCHED = ("profiles", "flows", "step_defs", "model_sets", "config", "prompts", "mcps", "application", "infrastructure", "domain", "composition_root")


def fingerprint(root):
    """The SHA-256 of every file of the folders a new profile must not need to touch."""
    digests = {}
    for folder in WATCHED:
        for base, dirs, files in os.walk(os.path.join(root, folder)):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                path = os.path.join(base, name)
                with open(path, "rb") as f:
                    digests[os.path.relpath(path, root)] = hashlib.sha256(f.read()).hexdigest()
    return digests


@pytest.fixture
def copy_of_the_configuration(tmp_path):
    for folder in ("profiles", "flows", "model_sets"):
        shutil.copytree(os.path.join(PROJECT_ROOT, folder), tmp_path / folder, ignore=shutil.ignore_patterns("_unverified"))
    os.makedirs(tmp_path / "config")
    shutil.copy(os.path.join(PROJECT_ROOT, "config", "state_fields.json"), tmp_path / "config" / "state_fields.json")
    return tmp_path


def write(root, relative, data):
    path = os.path.join(str(root), *relative.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data))


def agent_of(root):
    built = assemble(build_snapshot(FileConfigSource(str(root))))
    built.raise_on_errors()
    return built


def chat_like(name, token, **changes):
    """The `chat` profile of the repository under another name: the one new file."""
    with open(os.path.join(PROJECT_ROOT, "profiles", "chat.json"), encoding="utf-8") as f:
        data = json.load(f)
    data.update({"name": name, "about": f"A new profile, {name}.", "token_sha256": sha256_hex(token), **changes})
    return data


def classification(agent):
    """What a client sends as `inputs`: the Response `identification` returned."""
    service = MessageFlowService(outbound_port=ScriptedLLM(), mcp_list=[], agent=agent, profile="identification")
    service.text(TextRequestDTO(user_id="tester", session_id="s", content="hello"))
    return response_to_json(service.last_response)


class TestAProfileIsOneFile:
    def test_one_new_file_gives_a_profile_that_assembles(self, copy_of_the_configuration):
        before = len(agent_of(copy_of_the_configuration).profiles)
        write(copy_of_the_configuration, "profiles/mine.json", chat_like("mine", "mine-token"))
        agent = agent_of(copy_of_the_configuration)
        assert len(agent.profiles) == before + 1 and agent.profile("mine").flow_name == "conversation"

    def test_it_answers_with_the_models_the_file_names(self, copy_of_the_configuration):
        write(copy_of_the_configuration, "profiles/mine.json", chat_like("mine", "mine-token", models=["gemini-3.5-flash-lite"]))
        agent = agent_of(copy_of_the_configuration)
        llm = ScriptedLLM()
        service = SessionService(outbound_port=llm, mcp_list=[], agent=agent, response_reader=read_response_json)
        sid = service.start_session(StartSessionRequestDTO(user_id="tester", username="t")).session_id
        answer = service.message_received(MessageReceivedRequestDTO(
            user_id="tester", session_id=sid, message="hello", profile="mine", token="mine-token", inputs=classification(agent)))
        assert answer.success and answer.profile == "mine" and answer.response
        assert [c["format"].split("_response")[0] for c in llm.calls] == ["draft_writer_phase7", "editor_in_chief_phase8"]
        assert {c["model"] for c in llm.calls} == {"gemini-3.5-flash-lite"}

    def test_a_new_model_set_and_a_profile_that_names_it_are_two_files_and_no_code(self, copy_of_the_configuration):
        write(copy_of_the_configuration, "model_sets/mine_set.json", {"schema_version": 1, "default": ["gemini-3.5-flash-lite", "gemini-3-flash-preview"]})
        write(copy_of_the_configuration, "profiles/mine.json", chat_like("mine", "mine-token", models="mine_set"))
        agent = agent_of(copy_of_the_configuration)
        llm = ScriptedLLM()
        inputs = read_inputs(agent.profile("mine"), classification(agent), read_response_json)
        service = MessageFlowService(outbound_port=llm, mcp_list=[], agent=agent, profile="mine", inputs=inputs)
        service.text(TextRequestDTO(user_id="tester", session_id="s", content="hello"))
        assert {c["model"] for c in llm.calls} == {"gemini-3.5-flash-lite"}

    def test_a_new_flow_file_and_a_profile_that_names_it_run_without_any_python(self, copy_of_the_configuration):
        # T-05.12: the flow is only a list of steps that exist; the profile only names it
        write(copy_of_the_configuration, "flows/just_write.json", {
            "schema_version": 1, "name": "just_write", "about": "The editor alone.",
            "steps": [{"step": "draft_writer"}], "result_from": "draft_writer"})
        write(copy_of_the_configuration, "profiles/mine.json", chat_like("mine", "mine-token", flow="just_write"))
        agent = agent_of(copy_of_the_configuration)
        llm = ScriptedLLM()
        inputs = read_inputs(agent.profile("mine"), classification(agent), read_response_json)
        service = MessageFlowService(outbound_port=llm, mcp_list=[], agent=agent, profile="mine", inputs=inputs)
        service.text(TextRequestDTO(user_id="tester", session_id="s", content="hello"))
        assert [c["format"].split("_response")[0] for c in llm.calls] == ["draft_writer_phase7"]

    def test_a_flow_file_with_a_name_nobody_wrote_is_refused(self, copy_of_the_configuration):
        write(copy_of_the_configuration, "flows/bad.json", {
            "schema_version": 1, "name": "bad", "steps": [{"step": "draft_writer", "pause_if": "whenever"}], "result_from": "draft_writer"})
        built = assemble(build_snapshot(FileConfigSource(str(copy_of_the_configuration))))
        assert "unknown condition 'whenever'" in built.problems["flows/bad"][0] and "bad" not in built.flows

    def test_the_token_of_the_new_profile_is_the_only_one_that_opens_it(self, copy_of_the_configuration):
        write(copy_of_the_configuration, "profiles/mine.json", chat_like("mine", "mine-token"))
        agent = agent_of(copy_of_the_configuration)
        service = SessionService(outbound_port=ScriptedLLM(), mcp_list=[], agent=agent, response_reader=read_response_json)
        sid = service.start_session(StartSessionRequestDTO(user_id="tester", username="t")).session_id
        for token in ("chat-token", "", None):
            assert service.message_received(MessageReceivedRequestDTO(
                user_id="tester", session_id=sid, message="hello", profile="mine", token=token,
                inputs=classification(agent))).error_code == "INVALID_PROFILE"

    def test_a_file_with_a_mistake_is_refused_and_the_other_profiles_still_assemble(self, copy_of_the_configuration):
        write(copy_of_the_configuration, "profiles/broken.json", chat_like("broken", "x", flow="no-such-flow"))
        built = assemble(build_snapshot(FileConfigSource(str(copy_of_the_configuration))))
        assert "unknown flow 'no-such-flow'" in built.disabled()["broken"] and "chat" in built.profiles

    def test_nothing_of_the_repository_had_to_change(self, copy_of_the_configuration):
        before = fingerprint(PROJECT_ROOT)
        write(copy_of_the_configuration, "profiles/mine.json", chat_like("mine", "mine-token"))
        agent = agent_of(copy_of_the_configuration)
        MessageFlowService(outbound_port=ScriptedLLM(), mcp_list=[], agent=agent, profile="identification").text(
            TextRequestDTO(user_id="tester", session_id="s", content="hello"))
        assert fingerprint(PROJECT_ROOT) == before and "profiles/mine.json" not in {p.replace("\\", "/") for p in before}
