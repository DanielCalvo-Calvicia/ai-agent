# T-05.7: the seven profiles of today's flows and the service that runs ONE of them per message. The client's chain (identification,
# then the profile of the domain, then a gesture) is the tests' model in tests/brain_chain.py; here, the production side.
import os

import pytest

from application.engine.assemble import DEFAULT_PROFILE, assemble
from application.engine.config_snapshot import build_snapshot
from application.engine.state.expression_state import ExpressionFlowState
from application.engine.state.paused_run import PausedRun
from application.engine.support.metrics import SessionMetrics
from application.flows.profiles import ProfileMismatch, ProfileRunner
from application.flows.registry import FLOWS
from application.service.message_flow_service import MessageFlowService
from infrastructure.outbound.config.file_source import FileConfigSource
from infrastructure.outbound.llm.anthropic_schema import anthropic_schema_problems
from infrastructure.outbound.mcp.config import load_tool_snapshot
from application.inbound.dto.message import TextRequestDTO

from test_expression import feeling
from test_flow_golden import SCENARIOS, ScriptedLLM, TRIAGE
from test_resume import CHECK, Script, _verdict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
NAMES = ["identification", "chat", "special", "dynamics", "default", "movement", "gesture"]
MCP_LIST = [{"name": "dynamics_microservice", "type": "streamable_http", "config": {"url": "http://x"}},
            {"name": "aws_microservice", "type": "sse", "config": {"url": "http://y"}}]


@pytest.fixture(scope="module")
def agent():
    snapshot = build_snapshot(FileConfigSource(PROJECT_ROOT))
    built = assemble(snapshot, known_flows={flow.name for flow in FLOWS}, mcp_servers=load_tool_snapshot(),
                     schema_rules={"anthropic": anthropic_schema_problems})
    built.raise_on_errors()
    return built


def runner(llm, agent, mcp_list=None):
    return ProfileRunner(llm, MCP_LIST if mcp_list is None else mcp_list, SessionMetrics(), None, agent)


def models_by_step(llm):
    return {c["format"].split("_response")[0]: c["model"] for c in llm.calls}


# ===============================================
#  THE FILES
# ===============================================

class TestTheProfiles:
    def test_the_repository_has_exactly_these_seven_and_they_assemble(self, agent):
        assert sorted(agent.profiles) == sorted(NAMES) and agent.problems == {}

    def test_the_ten_generic_profiles_are_kept_aside_and_not_loaded(self, agent):
        folder = os.path.join(PROJECT_ROOT, "profiles", "_unverified")
        assert len([n for n in os.listdir(folder) if n.endswith(".json")]) == 10
        assert "claude_haiku" not in agent.profiles and "budget50" not in agent.profiles

    def test_every_profile_but_default_has_a_token_hash_and_default_has_none(self, agent):
        assert "token_sha256" not in agent.profile(DEFAULT_PROFILE).definition
        assert all(len(p.definition["token_sha256"]) == 64 for n, p in agent.profiles.items() if n != DEFAULT_PROFILE)

    def test_no_profile_holds_a_real_token_hash_yet(self, agent):
        # the files hold a placeholder (no token has this SHA-256) until the maintainer writes the hash of each token
        assert {p.definition.get("token_sha256") for p in agent.profiles.values()} - {None} == {"0" * 64}

    @pytest.mark.parametrize("name, flow", [("identification", "identification"), ("chat", "conversation"), ("special", "special"),
                                            ("dynamics", "special"), ("default", "special"), ("movement", "movement"),
                                            ("gesture", "expression")])
    def test_each_profile_names_the_flow_it_runs(self, agent, name, flow):
        assert agent.profile(name).flow_name == flow

    def test_the_models_of_each_profile(self, agent):
        sets = {n: p.definition["models"] for n, p in agent.profiles.items()}
        assert sets == {"identification": "proven", "chat": "claude_haiku", "special": "claude_mixed", "dynamics": "claude_mixed",
                        "default": "proven", "movement": "proven", "gesture": "proven"}

    def test_identification_answers_with_the_whole_response_and_the_others_with_text(self, agent):
        assert {n: p.default_return for n, p in agent.profiles.items()} == {n: ("full" if n == "identification" else "text") for n in NAMES}

    def test_the_inputs_each_profile_declares(self, agent):
        assert agent.profile("chat").requires == ["user_goal", "task_category"]
        assert agent.profile("gesture").requires == ["reply"]
        assert agent.profile("special").requires == [] and agent.profile("default").requires == []


class TestTheToolsOfEachProfile:
    def servers(self, agent, name):
        return [s["name"] for s in runner(ScriptedLLM(), agent)._servers(agent.profile(name))]

    def test_special_has_every_server(self, agent):
        assert self.servers(agent, "special") == ["dynamics_microservice", "aws_microservice"]

    def test_dynamics_has_only_the_dynamics_server(self, agent):
        assert self.servers(agent, "dynamics") == ["dynamics_microservice"]

    @pytest.mark.parametrize("name", ["default", "identification", "chat", "movement", "gesture"])
    def test_the_others_have_no_tools_and_default_never_reaches_business_data(self, agent, name):
        assert self.servers(agent, name) == []


# ===============================================
#  EACH PROFILE RUNS ITS FLOW
# ===============================================

class TestEachProfileRunsItsFlow:
    def test_identification_only_classifies_and_gives_back_the_state(self, agent):
        llm = ScriptedLLM()
        result = runner(llm, agent).run("identification", "what is the weather")
        assert result.flow == "identification" and result.reply == "" and result.state.task_category is not None
        assert [c["format"] for c in llm.calls] == [TRIAGE]

    def test_special_does_its_own_triage_first_and_uses_its_models(self, agent):
        scenario = SCENARIOS["no_actions"]
        llm = ScriptedLLM(**scenario["llm"])
        result = runner(llm, agent).run("special", scenario["message"])
        assert result.flow == "special" and result.reply
        assert llm.calls[0]["format"] == TRIAGE
        models = models_by_step(llm)
        assert models["project_manager_phase2"] == "claude-sonnet-5-5" and models["triage_specialist_phase1"] == "claude-haiku-4-5"
        assert models["editor_in_chief_phase8"] == "claude-sonnet-5-5"

    def test_asking_identification_and_then_special_runs_the_triage_twice_and_says_nothing(self, agent):
        scenario = SCENARIOS["no_actions"]
        llm = ScriptedLLM(**scenario["llm"])
        run = runner(llm, agent)
        run.run("identification", scenario["message"])
        run.run("special", scenario["message"])
        assert [c["format"] for c in llm.calls].count(TRIAGE) == 2

    def test_chat_runs_the_writer_and_the_editor_on_the_state_it_is_given(self, agent):
        llm = ScriptedLLM()
        identified = runner(llm, agent).run("identification", "hello").state
        llm2 = ScriptedLLM()
        state = ProfileRunner(llm2, [], SessionMetrics(), None, agent).flows["conversation"].new_state("hello", [])
        state.take_over(identified)
        result = runner(llm2, agent).run("chat", "hello", state=state)
        assert result.flow == "conversation" and [c["format"].split("_response")[0] for c in llm2.calls] == ["draft_writer_phase7", "editor_in_chief_phase8"]
        assert models_by_step(llm2)["draft_writer_phase7"] == "claude-haiku-4-5"

    def test_default_runs_the_whole_text_chain_with_the_models_of_proven(self, agent):
        scenario = SCENARIOS["no_actions"]
        llm = ScriptedLLM(**scenario["llm"])
        result = runner(llm, agent).run("default", scenario["message"])
        assert result.flow == "special" and {c["model"] for c in llm.calls} == {"gemini-3.1-flash-lite"}

    def test_movement_plans_and_validates(self, agent):
        scenario = SCENARIOS["movement_goes_to_the_movement_flow_and_is_announced"]
        llm = ScriptedLLM(**scenario["llm"])
        identified = runner(ScriptedLLM(**scenario["llm"]), agent).run("identification", scenario["message"]).state
        flow = runner(llm, agent).flows["movement"]
        state = flow.new_state(scenario["message"], [])
        state.take_over(identified)
        result = runner(llm, agent).run("movement", scenario["message"], state=state)
        assert result.flow == "movement"

    def test_gesture_reads_the_reply_it_is_given(self, agent):
        llm = ScriptedLLM(overrides=feeling())
        state = ExpressionFlowState(message="hello", reply="Hello! How can I help you today?", speech_seconds=2.0)
        result = runner(llm, agent).run("gesture", "hello", state=state)
        assert result.flow == "expression" and result.gesture is True


# ===============================================
#  ONE PROFILE PER MESSAGE
# ===============================================

class TestTheServiceRunsOneProfile:
    def test_a_message_runs_the_default_profile(self, agent):
        scenario = SCENARIOS["no_actions"]
        llm = ScriptedLLM(**scenario["llm"])
        response = MessageFlowService(outbound_port=llm, mcp_list=MCP_LIST, agent=agent).text(
            TextRequestDTO(user_id="tester", session_id="s", content=scenario["message"]))
        assert response.success and response.flow == "special" and response.content
        assert llm.calls[0]["format"] == TRIAGE and {c["model"] for c in llm.calls} == {"gemini-3.1-flash-lite"}

    def test_a_service_can_be_asked_another_profile(self, agent):
        llm = ScriptedLLM()
        service = MessageFlowService(outbound_port=llm, mcp_list=[], agent=agent, profile="identification")
        assert service.text(TextRequestDTO(user_id="tester", session_id="s", content="hi")).flow == "identification"

    def test_there_is_no_gesture_and_no_choice_between_flows_in_the_service(self, agent):
        scenario = SCENARIOS["communication_goes_to_the_conversation_flow"]
        llm = ScriptedLLM(**scenario["llm"])
        response = MessageFlowService(outbound_port=llm, mcp_list=[], agent=agent).text(
            TextRequestDTO(user_id="tester", session_id="s", content=scenario["message"]))
        assert response.flow == "special" and response.gesture is False and list(response.movements) == []

    def test_a_service_with_no_agent_says_so(self):
        service = MessageFlowService(outbound_port=ScriptedLLM(), mcp_list=[])
        with pytest.raises(ValueError, match="no agent"):
            service.main_flow("hi")

    def test_an_unknown_profile_is_refused(self, agent):
        with pytest.raises(KeyError):
            runner(ScriptedLLM(), agent).run("nope", "hi")

    def test_a_profile_that_lists_its_own_steps_waits_for_steps_as_files(self, agent):
        from dataclasses import replace
        own = replace(agent.profile("chat"), name="mine", flow_name=None, steps=["draft_writer"])
        agent2 = type(agent)({**agent.profiles, "mine": own}, {})
        with pytest.raises(ValueError, match="T-05.16"):
            runner(ScriptedLLM(), agent2).run("mine", "hi")


class TestARunThatAsksTheUser:
    def paused_run(self, agent):
        scenario = SCENARIOS["pause_after_project_manager"]
        llm = ScriptedLLM(**scenario["llm"])
        result = runner(llm, agent).run("special", scenario["message"])
        assert result.paused is not None and result.flow == "special"
        return result.paused

    def test_the_answer_goes_to_the_profile_that_asked(self, agent):
        paused = self.paused_run(agent)
        assert isinstance(paused, PausedRun) and paused.flow == "special"
        result = runner(ScriptedLLM(overrides={CHECK: Script(_verdict("answered", "Ana"))}), agent).run("special", "to Ana", paused=paused)
        assert result.flow == "special" and result.paused is None and result.reply

    def test_another_profile_cannot_take_the_answer(self, agent):
        paused = self.paused_run(agent)
        with pytest.raises(ProfileMismatch, match="belongs to the flow 'special', not to profile 'chat'"):
            runner(ScriptedLLM(), agent).run("chat", "to Ana", paused=paused)

    def test_dynamics_and_default_share_the_flow_so_either_can_take_the_answer(self, agent):
        paused = self.paused_run(agent)
        result = runner(ScriptedLLM(overrides={CHECK: Script(_verdict("answered", "Ana"))}), agent).run("dynamics", "to Ana", paused=paused)
        assert result.flow == "special" and result.paused is None
