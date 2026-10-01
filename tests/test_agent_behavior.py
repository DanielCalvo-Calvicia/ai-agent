"""
Behavior of the pieces around the flow: settings, provider resolution, MCP tools,
the HTTP layer, session memory, per-phase models and prompt loading.
No real LLM, network or MCP server is used.
"""
import os
import sys
import threading
from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.orchestration.support.model_selection import model_for_phase
from application.service.session_service import SessionService
from application.system_prompts.advanced import LoadSystemPrompt
from domain.entities.payload import Payload
from domain.entities.response import Response
from domain.value_objects.model import GithubModels, get_selected_model
from domain.value_objects.tool import ToolDefinition
from infrastructure.inbound.http.fastapi import SessionFastAPI
from infrastructure.outbound.llm.config import VercelAIConfig
from infrastructure.outbound.llm.vercel import VercelAIAdapter
from infrastructure.outbound.llm.provider_models import ErrProviderNotSupported, resolve_provider_model
from infrastructure.outbound.llm.tools import resolve_tools
from infrastructure.outbound.mcp.config import load_mcp_configs
from infrastructure.outbound.mcp.tool_executor import MCPToolExecutor

from test_flow_golden import ScriptedLLM


@pytest.fixture(autouse=True)
def _project_cwd(monkeypatch):
    monkeypatch.chdir(PROJECT_ROOT)


# ===============================================
#  SETTINGS
# ===============================================

class TestConfigFromEnv:
    def test_reads_the_environment_when_called(self, monkeypatch):
        monkeypatch.delenv("GITHUB_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
        monkeypatch.setenv("GITHUB_PAT", "github-pat")
        monkeypatch.setenv("GITHUB_URL", "https://models.example/inference")
        monkeypatch.setenv("OLLAMA_URL", "http://ollama.example/v1")

        config = VercelAIConfig.from_env()

        assert config.openai_api_key == "openai-key"
        assert config.github_api_key == "github-pat"
        assert config.github_url == "https://models.example/inference"
        assert config.OLLAMA_URL == "http://ollama.example/v1"

    def test_github_pat_wins_over_the_old_name(self, monkeypatch):
        monkeypatch.setenv("GITHUB_PAT", "new")
        monkeypatch.setenv("GITHUB_API_KEY", "old")
        assert VercelAIConfig.from_env().github_api_key == "new"

    def test_old_github_name_still_works(self, monkeypatch):
        monkeypatch.delenv("GITHUB_PAT", raising=False)
        monkeypatch.setenv("GITHUB_API_KEY", "old")
        assert VercelAIConfig.from_env().github_api_key == "old"

    def test_missing_variables_become_empty_strings(self, monkeypatch):
        for name in ("OPENAI_API_KEY", "GITHUB_PAT", "GITHUB_API_KEY", "GITHUB_URL"):
            monkeypatch.delenv(name, raising=False)
        config = VercelAIConfig.from_env()
        assert config.openai_api_key == ""
        assert config.github_url == ""

    def test_passes_the_tool_executor_through(self):
        marker = object()
        assert VercelAIConfig.from_env(tool_executor=marker).tool_executor is marker


class TestVercelAdapterAvailability:
    def test_unavailable_with_no_provider_configured(self):
        assert VercelAIAdapter(Config=VercelAIConfig()).is_available() is False

    @pytest.mark.parametrize("field", [
        "openai_api_key", "anthropic_api_key", "google_api_key", "mistral_api_key",
        "groq_api_key", "cohere_api_key", "github_api_key", "OLLAMA_URL",
    ])
    def test_available_when_any_single_provider_setting_is_present(self, field):
        config = VercelAIConfig(**{field: "set"})
        assert VercelAIAdapter(Config=config).is_available() is True

    def test_no_network_call_is_made(self, monkeypatch):
        def _fail(*args, **kwargs):
            raise AssertionError("is_available must not call the LLM")

        monkeypatch.setattr("infrastructure.outbound.llm.vercel.generate_text", _fail)
        VercelAIAdapter(Config=VercelAIConfig(openai_api_key="k")).is_available()


# ===============================================
#  PROVIDER RESOLUTION
# ===============================================

class TestProviderResolution:
    def test_github_models_use_the_github_url_and_key(self):
        config = VercelAIConfig(github_api_key="pat", github_url="https://models.example/inference")
        model = resolve_provider_model(get_selected_model(GithubModels.GPT_4_1), config, {})
        assert str(model._client.base_url).startswith("https://models.example/inference")
        assert model._client.api_key == "pat"

    def test_ollama_uses_the_configured_url_instead_of_raising_key_error(self):
        config = VercelAIConfig(OLLAMA_URL="http://ollama.example/v1")
        model = resolve_provider_model(get_selected_model("llama3.3"), config, {})
        assert str(model._client.base_url).startswith("http://ollama.example/v1")

    def test_sampling_options_are_passed_to_the_model(self):
        config = VercelAIConfig(github_api_key="pat", github_url="https://models.example/inference")
        model = resolve_provider_model(
            get_selected_model(GithubModels.GPT_4_1), config, {"temperature": 0.3, "max_tokens": 50}
        )
        assert model._default_kwargs == {"temperature": 0.3, "max_tokens": 50}


# ===============================================
#  MCP TOOLS
# ===============================================

class FakeExecutor:
    def __init__(self, tools: Dict[str, List[ToolDefinition]]):
        self.tools = tools
        self.executed: List[Any] = []

    def list_tools(self, server_name: str):
        return self.tools.get(server_name, [])

    def execute(self, name: str, args: Dict[str, Any]):
        self.executed.append((name, args))
        return {"result": "done", "is_error": False}


SERVER = {"name": "aws", "type": "sse", "config": {"type": "sse", "url": "http://example.invalid/sse"}}
TOOL = ToolDefinition(name="get_file", description="d", parameters={"type": "object", "properties": {}})


class TestResolveTools:
    def test_no_tools(self):
        assert resolve_tools(VercelAIConfig(), []) == []
        assert resolve_tools(VercelAIConfig(), None) == []

    def test_server_descriptor_without_executor_is_skipped_not_a_crash(self):
        assert resolve_tools(VercelAIConfig(), [SERVER]) == []

    def test_server_descriptor_expands_into_the_tools_of_that_server(self):
        executor = FakeExecutor({"aws": [TOOL]})
        tools = resolve_tools(VercelAIConfig(tool_executor=executor), [SERVER])
        assert [t.name for t in tools] == ["get_file"]

    def test_expanded_tool_runs_through_the_executor(self):
        executor = FakeExecutor({"aws": [TOOL]})
        tools = resolve_tools(VercelAIConfig(tool_executor=executor), [SERVER])
        tools[0].handler(path="/a")
        assert executor.executed == [("get_file", {"path": "/a"})]

    def test_server_with_no_tools_gives_no_tools(self):
        assert resolve_tools(VercelAIConfig(tool_executor=FakeExecutor({})), [SERVER]) == []

    def test_tool_definition_is_wrapped(self):
        executor = FakeExecutor({})
        tools = resolve_tools(VercelAIConfig(tool_executor=executor), [TOOL])
        assert [t.name for t in tools] == ["get_file"]
        tools[0].handler(x=1)
        assert executor.executed == [("get_file", {"x": 1})]


class FakeClientManager:
    def __init__(self, configs, fail=False):
        self.configs = {c["name"]: c for c in configs}
        self.fail = fail

    def session_scope(self, server_name):
        raise ConnectionError("server down")


class TestMCPToolExecutor:
    def test_unreachable_server_yields_no_tools(self):
        executor = MCPToolExecutor(FakeClientManager([SERVER]))
        assert executor.list_tools("aws") == []

    def test_unsupported_protocol_yields_no_tools(self):
        stdio = {"name": "fetch", "type": "stdio", "config": {"type": "stdio", "command": "docker"}}
        executor = MCPToolExecutor(FakeClientManager([stdio]))
        assert executor.list_tools("fetch") == []

    def test_unknown_server_yields_no_tools(self):
        assert MCPToolExecutor(FakeClientManager([])).list_tools("nope") == []

    def test_unknown_tool_is_an_error_result(self):
        executor = MCPToolExecutor(FakeClientManager([SERVER]))
        result = executor.execute("missing", {})
        assert result["is_error"] is True


class TestMcpConfigLoading:
    def test_loads_the_project_mcps_from_any_working_directory(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        configs = load_mcp_configs()
        names = {c["name"] for c in configs}
        assert "aws_microservice" in names
        aws = next(c for c in configs if c["name"] == "aws_microservice")
        assert aws["type"] == "sse"
        assert aws["config"]["url"].endswith("/mcp/sse")

    def test_missing_folder_gives_an_empty_list(self, tmp_path):
        assert load_mcp_configs(str(tmp_path / "does-not-exist")) == []


# ===============================================
#  HTTP LAYER
# ===============================================

class ThreadRecordingLLM(ScriptedLLM):
    def ask(self, Payload: Payload) -> Response:
        self.threads = getattr(self, "threads", set())
        self.threads.add(threading.get_ident())
        return super().ask(Payload)


class FailingLLM(ScriptedLLM):
    def ask(self, Payload: Payload) -> Response:
        raise RuntimeError("provider exploded")


def _client(llm) -> TestClient:
    app = FastAPI()
    SessionFastAPI(App=app, SessionPort=SessionService(outbound_port=llm, mcp_list=[]))
    return TestClient(app)


def _start(client: TestClient) -> str:
    response = client.post("/session/start", json={"user_id": "tester", "username": "t"})
    return response.json()["data"]["session_id"]


class _UnavailableLLM(ScriptedLLM):
    def is_available(self) -> bool:
        return False


class TestHttp:
    def test_health(self):
        response = _client(ScriptedLLM()).get("/health")
        body = response.json()
        assert response.status_code == 200
        assert body["action"] == "health"
        assert body["status"] == "success"
        assert body["data"]["healthy"] is True

    def test_available_when_a_provider_is_configured(self):
        response = _client(ScriptedLLM()).get("/available")
        body = response.json()
        assert response.status_code == 200
        assert body["action"] == "check_availability"
        assert body["status"] == "success"
        assert body["data"] == {"is_available": True, "reason": None}

    def test_available_when_no_provider_is_configured(self):
        response = _client(_UnavailableLLM()).get("/available")
        body = response.json()
        assert response.status_code == 200
        assert body["data"]["is_available"] is False
        assert body["data"]["reason"]

    def test_message_flow_runs_off_the_event_loop_thread(self):
        llm = ThreadRecordingLLM()
        client = _client(llm)
        session_id = _start(client)
        loop_threads = set()

        # The TestClient runs the app's event loop in its own portal thread.
        # The flow must run in a different (worker) thread.
        original = SessionService.message_received

        def spy(self, request):
            loop_threads.add(threading.get_ident())
            return original(self, request)

        SessionService.message_received = spy
        try:
            client.post("/session/message", json={"user_id": "tester", "session_id": session_id, "message": "hi"})
        finally:
            SessionService.message_received = original

        assert llm.threads
        assert loop_threads == llm.threads          # message_received ran where the LLM was called
        assert threading.get_ident() not in llm.threads

    def test_successful_message_returns_the_reply(self):
        client = _client(ScriptedLLM())
        session_id = _start(client)
        body = client.post(
            "/session/message", json={"user_id": "tester", "session_id": session_id, "message": "hi"}
        ).json()
        assert body["status"] == "success"
        assert body["data"]["success"] is True
        assert body["data"]["response"] == "final answer"

    def test_failure_is_an_error_and_the_reply_is_an_apology(self):
        llm = FailingLLM()
        client = _client(llm)
        session_id = _start(client)
        body = client.post(
            "/session/message", json={"user_id": "tester", "session_id": session_id, "message": "hi"}
        ).json()
        assert body["status"] == "error"
        assert body["data"]["success"] is False
        assert body["data"]["response"].startswith("Sorry")
        assert "What happened:" in body["data"]["response"] and "Why:" in body["data"]["response"]
        assert "provider exploded" not in body["data"]["response"]      # raw error text is never spoken
        assert "RuntimeError" in body["data"]["message"]                # but the technical reason is kept

    def test_unknown_session_is_an_error_with_an_apology(self):
        body = _client(ScriptedLLM()).post(
            "/session/message", json={"user_id": "tester", "session_id": "nope", "message": "hi"}
        ).json()
        assert body["status"] == "error"
        assert body["data"]["response"].startswith("Sorry, I could not find this conversation")
        assert "not found" in body["data"]["message"].lower()


# ===============================================
#  SESSION MEMORY
# ===============================================

TRIAGE = "triage_specialist_phase1_response_format"
PM = "project_manager_phase2_response_format"


def _triage_inputs(llm: ScriptedLLM) -> List[str]:
    return [c["user_message"] for c in llm.calls if c["format"] == TRIAGE]


def _pm_inputs(llm: ScriptedLLM) -> List[str]:
    return [c["user_message"] for c in llm.calls if c["format"] == PM]


def _say(service: SessionService, session_id: str, text: str):
    from application.inbound.dto.session import MessageReceivedRequestDTO
    return service.message_received(
        MessageReceivedRequestDTO(user_id="tester", session_id=session_id, message=text)
    )


def _service(llm, **kwargs) -> tuple:
    from application.inbound.dto.session import StartSessionRequestDTO
    service = SessionService(outbound_port=llm, mcp_list=[], **kwargs)
    session_id = service.start_session(StartSessionRequestDTO(user_id="tester", username="t")).session_id
    return service, session_id


class TestSessionMemory:
    def test_first_message_has_no_history(self):
        llm = ScriptedLLM()
        service, sid = _service(llm)
        _say(service, sid, "what is the weather")
        assert _triage_inputs(llm) == ["what is the weather"]
        assert "conversation_history" not in _pm_inputs(llm)[0]

    def test_second_message_sees_the_first_exchange(self):
        llm = ScriptedLLM()
        service, sid = _service(llm)
        _say(service, sid, "my name is Ana")
        _say(service, sid, "what is my name?")
        second = _triage_inputs(llm)[1]
        assert "user: my name is Ana" in second
        assert "assistant: final answer" in second
        assert second.endswith("Current user message:\nwhat is my name?")
        assert "conversation_history" in _pm_inputs(llm)[1]

    def test_history_is_per_session(self):
        llm = ScriptedLLM()
        service, sid_a = _service(llm)
        from application.inbound.dto.session import StartSessionRequestDTO
        sid_b = service.start_session(StartSessionRequestDTO(user_id="tester", username="b")).session_id
        _say(service, sid_a, "secret of A")
        _say(service, sid_b, "hello from B")
        assert _triage_inputs(llm)[1] == "hello from B"

    def test_only_the_last_turns_are_kept(self):
        llm = ScriptedLLM()
        service, sid = _service(llm, history_turns=2)
        for text in ("one", "two", "three", "four"):
            _say(service, sid, text)
        last = _triage_inputs(llm)[3]
        assert "user: three" in last and "user: two" in last
        assert "user: one" not in last

    def test_zero_turns_disables_memory(self):
        llm = ScriptedLLM()
        service, sid = _service(llm, history_turns=0)
        _say(service, sid, "one")
        _say(service, sid, "two")
        assert _triage_inputs(llm)[1] == "two"

    def test_a_paused_flow_is_continued_by_the_next_message(self):
        pm_calls = []

        def pause_only_the_first_time(payload):
            pm_calls.append(payload)
            if len(pm_calls) > 1:
                return None      # the default plan: proceed
            return {"actions": [], "task_category_complexity": "low",
                    "next_step": {"ready_to_execute": False, "status": "awaiting_user_input",
                                  "recommended_action": "", "blocking_reason": "",
                                  "requested_user_input": ["who is the recipient?"]}}

        llm = ScriptedLLM(overrides={PM: pause_only_the_first_time})
        service, sid = _service(llm)
        first = _say(service, sid, "send an email")
        assert first.response == "Please tell me the missing details."   # the clarification question
        second = _say(service, sid, "recipient is Bob")
        assert len(_triage_inputs(llm)) == 1                             # triage did not run again
        assert second.response == "final answer"

    def test_failed_message_is_not_remembered(self):
        llm = FailingLLM()
        service, sid = _service(llm)
        assert _say(service, sid, "boom").success is False
        assert service.sessions[sid].history == []


# ===============================================
#  MODELS PER PHASE AND PROMPTS
# ===============================================

class TestModelPerPhase:
    def test_default_is_used_without_override(self, monkeypatch):
        monkeypatch.delenv("AI_AGENT_MODEL_PHASE_2", raising=False)
        assert model_for_phase(2, GithubModels.GPT_4_1).id == "gpt-4.1"

    def test_override_replaces_the_default(self, monkeypatch):
        monkeypatch.setenv("AI_AGENT_MODEL_PHASE_2", "gpt-4.1-mini")
        assert model_for_phase(2, GithubModels.GPT_4_1).id == "gpt-4.1-mini"

    def test_override_of_one_phase_does_not_touch_the_others(self, monkeypatch):
        monkeypatch.setenv("AI_AGENT_MODEL_PHASE_2", "gpt-4.1-mini")
        monkeypatch.delenv("AI_AGENT_MODEL_PHASE_3", raising=False)
        assert model_for_phase(3, GithubModels.GPT_4_1).id == "gpt-4.1"

    def test_a_model_of_another_provider_can_be_used(self, monkeypatch):
        monkeypatch.setenv("AI_AGENT_MODEL_PHASE_2", "gemini-2.5-flash")
        model = model_for_phase(2, GithubModels.GPT_4_1)
        assert model.id == "gemini-2.5-flash" and model.is_google()

    def test_unknown_override_fails_loudly(self, monkeypatch):
        monkeypatch.setenv("AI_AGENT_MODEL_PHASE_2", "not-a-model")
        with pytest.raises(ValueError, match="AI_AGENT_MODEL_PHASE_2"):
            model_for_phase(2, GithubModels.GPT_4_1)

    def test_override_reaches_the_llm_call(self, monkeypatch):
        monkeypatch.setenv("AI_AGENT_MODEL_PHASE_1", "gpt-4.1-nano")
        llm = ScriptedLLM()
        service, sid = _service(llm)
        _say(service, sid, "hi")
        assert llm.calls[0]["model"] == "gpt-4.1-nano"


class TestPrompts:
    def test_prompts_load_from_any_working_directory(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        for phase in range(0, 10):
            assert LoadSystemPrompt(phase)

    def test_prompts_are_read_as_utf8(self):
        assert "SYSTEM INVARIANTS — APPLIES TO ALL PHASES" in LoadSystemPrompt(0)

    def test_unknown_phase_has_no_prompt(self):
        assert LoadSystemPrompt(42) is None


# ===============================================
#  ACTION ORDER, EXPLICIT (the golden test records the same runs in full)
# ===============================================

from test_flow_golden import SCENARIOS, _run  # noqa: E402


def _phases(run):
    return [c["format"].split("_")[0] for c in run["calls"] if c["format"].startswith("phase")]


class TestActionOrder:
    def test_an_mcp_result_reaches_the_action_that_depends_on_it(self):
        run = _run(SCENARIOS["mcp_result_feeds_a_cognitive_action"])
        assert _phases(run) == ["phase5", "phase6", "phase4"]         # tool, clean, then the dependent
        worker_input = next(c for c in run["calls"] if c["format"].startswith("phase4"))["user_message"]
        assert "'dependency_outputs': {'1': 'out-p6-1'}" in worker_input

    def test_children_run_before_their_parent_and_dependencies_before_dependents(self):
        run = _run(SCENARIOS["action_with_subactions"])
        ids = [c["user_message"].split("Id(value='")[1].split("'")[0]
               for c in run["calls"] if c["format"].startswith("phase")]
        assert ids == ["1.1", "1.2", "1", "2"]

    def test_only_mcp_results_are_cleaned(self):
        run = _run(SCENARIOS["full_path_with_mcp"])
        assert _phases(run) == ["phase4", "phase5", "phase6"]

    def test_a_failing_tool_is_tried_as_many_times_as_the_setting_says(self, monkeypatch):
        monkeypatch.setenv("AI_AGENT_MAX_ATTEMPTS", "2")
        run = _run(SCENARIOS["mcp_tool_fails_then_dependents_are_skipped"])
        assert _phases(run) == ["phase5", "phase5", "phase4"]         # 2 tries, then only the independent action

    def test_a_failing_tool_is_tried_three_times_by_default_and_its_dependents_are_skipped(self, monkeypatch):
        monkeypatch.delenv("AI_AGENT_MAX_ATTEMPTS", raising=False)
        run = _run(SCENARIOS["mcp_tool_fails_then_dependents_are_skipped"])
        assert _phases(run) == ["phase5", "phase5", "phase5", "phase4"]
        draft_input = next(c for c in run["calls"] if c["format"].startswith("draft"))["user_message"]
        assert "tool unavailable" in draft_input
        assert "skipped because a step it needs failed" in draft_input

    def test_unknown_and_circular_dependencies_fail_only_those_actions(self):
        run = _run(SCENARIOS["unknown_and_circular_dependencies"])
        assert _phases(run) == ["phase4"]                             # only action 4 could run
        draft_input = next(c for c in run["calls"] if c["format"].startswith("draft"))["user_message"]
        assert "unknown steps: 9" in draft_input
        assert "circular or unknown dependencies" in draft_input

    def test_blocked_mcp_actions_make_no_call(self):
        run = _run(SCENARIOS["mcp_blocked_by_confirmation"])
        assert _phases(run) == ["phase4"]

    def test_triage_can_pause_the_flow(self):
        run = _run(SCENARIOS["pause_after_triage"])
        assert [c["format"] for c in run["calls"]] == ["triage_specialist_phase1_response_format", "<text>"]
        assert "What do you want me to do?" in run["calls"][-1]["user_message"]
