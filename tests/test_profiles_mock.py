# T-05.10: `default` and `dynamics` run the steps of `special`, so they have no golden block of their own; here they run on a scripted LLM
# and what makes them different is checked: the tools, the models and the token.
import dataclasses
import os

import pytest

from application.assembly.assemble import assemble
from application.runtime.profile.assembled import Agent
from application.assembly.config_snapshot import build_snapshot
from application.runtime.profile.access import sha256_hex
from application.dtos.inbound.message import TextRequestDTO
from application.dtos.inbound.session import MessageReceivedRequestDTO, StartSessionRequestDTO
from application.service.message_flow_service import MessageFlowService
from application.service.session_service import SessionService
from infrastructure.outbound.config.file_source import FileConfigSource
from domain.value_objects.llm_request.model import GoogleModels
from application.mappers.outbound.response_mapper import read_response_json
from test_flow_golden import SCENARIOS, ScriptedLLM

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SERVERS = [{"name": "dynamics_microservice", "type": "streamable_http", "config": {"url": "http://dynamics.invalid"}},
           {"name": "aws_microservice", "type": "sse", "config": {"url": "http://aws.invalid"}}]


@pytest.fixture(scope="module")
def agent():
    built = assemble(build_snapshot(FileConfigSource(PROJECT_ROOT)))
    built.raise_on_errors()
    profiles = {}
    for name, profile in built.profiles.items():
        definition = dict(profile.definition)
        if name != "default":
            definition["token_sha256"] = sha256_hex(f"{name}-token")
        profiles[name] = dataclasses.replace(profile, definition=definition)
    return Agent(profiles, {}, built.flows, built.step_defs, built.step_prompts)


def run(agent, profile, scenario="full_path_with_mcp"):
    sc = SCENARIOS[scenario]
    llm = ScriptedLLM(**sc["llm"])
    service = MessageFlowService(outbound_port=llm, mcp_list=SERVERS, agent=agent, profile=profile)
    answer = service.text(TextRequestDTO(user_id="tester", session_id="s", content=sc["message"]))
    return llm, answer


def formats(llm):
    return [c["format"].split("_response")[0] for c in llm.calls]


def planner(llm):
    return next(c for c in llm.calls if c["format"].startswith("project_manager"))


def tools_given(llm):
    return " ".join(c["tools"] for c in llm.calls)


# ===============================================
#  THE SAME STEPS AS SPECIAL
# ===============================================

class TestTheStepsAreThoseOfSpecial:
    @pytest.mark.parametrize("profile", ["default", "dynamics"])
    def test_the_steps_and_their_order_are_the_steps_of_special(self, agent, profile):
        assert formats(run(agent, profile)[0]) == formats(run(agent, "special")[0])
        assert formats(run(agent, profile)[0])[:2] == ["triage_specialist_phase1", "project_manager_phase2"]

    @pytest.mark.parametrize("profile", ["default", "dynamics"])
    def test_the_answer_comes_from_the_special_flow(self, agent, profile):
        llm, answer = run(agent, profile, "no_actions")
        assert answer.success and answer.flow == "special" and answer.content


# ===============================================
#  THE TOOLS
# ===============================================

class TestTheTools:
    def test_special_shows_every_server_to_the_planner_and_gives_their_tools_to_the_operator(self, agent):
        llm, _ = run(agent, "special")
        assert "dynamics_microservice" in planner(llm)["user_message"] and "aws_microservice" in planner(llm)["user_message"]
        assert "dynamics.invalid" in tools_given(llm) and "aws.invalid" in tools_given(llm)

    def test_dynamics_shows_and_gives_only_the_dynamics_server(self, agent):
        llm, _ = run(agent, "dynamics")
        assert "dynamics_microservice" in planner(llm)["user_message"] and "aws_microservice" not in planner(llm)["user_message"]
        assert "dynamics.invalid" in tools_given(llm) and "aws.invalid" not in tools_given(llm)

    def test_default_shows_no_server_and_no_call_has_a_tool_even_when_the_plan_asks_for_one(self, agent):
        llm, answer = run(agent, "default")           # the scripted plan has a tool action: the operator gets no tool to call
        assert "dynamics_microservice" not in planner(llm)["user_message"] and "aws_microservice" not in planner(llm)["user_message"]
        assert set(c["tools"] for c in llm.calls) == {"[]"}
        assert answer.success


# ===============================================
#  THE MODELS
# ===============================================

class TestTheModels:
    def test_default_runs_every_step_on_the_proven_set(self, agent):
        llm, _ = run(agent, "default")
        assert {c["model"] for c in llm.calls} == {"gemini-3.1-flash-lite"}

    def test_dynamics_runs_on_claude_mixed(self, agent):
        llm, _ = run(agent, "dynamics")
        by_step = {c["format"].split("_response")[0]: c["model"] for c in llm.calls}
        assert by_step["project_manager_phase2"] == "claude-sonnet-5-5" and by_step["draft_writer_phase7"] == "claude-sonnet-5-5"
        assert by_step["editor_in_chief_phase8"] == "claude-sonnet-5-5"
        assert by_step["triage_specialist_phase1"] == "claude-haiku-4-5" and by_step["safety_quality_gatekeeper_phase3"] == "claude-haiku-4-5"

    def test_dynamics_and_special_use_the_same_models_and_the_default_does_not(self, agent):
        models = lambda profile: [c["model"] for c in run(agent, profile)[0].calls]       # noqa: E731
        assert models("dynamics") == models("special") and models("default") != models("special")

    @pytest.mark.parametrize("profile", ["special", "dynamics", "chat"])
    def test_the_claude_profiles_have_no_fallback_so_customer_data_stays_with_one_provider(self, agent, profile):
        for step in ("triage_specialist", "project_manager", "draft_writer", "editor_in_chief"):
            models = agent.profile(profile).resolver.models_for("special", step, GoogleModels.GEMINI_3_6_FLASH)
            assert len(models) == 1 and models[0].is_anthropic(), (profile, step)


# ===============================================
#  THE TOKEN, THROUGH THE SERVICE
# ===============================================

def service(llm, agent):
    return SessionService(outbound_port=llm, mcp_list=SERVERS, agent=agent, response_reader=read_response_json)


def ask(svc, sid, **fields):
    return svc.message_received(MessageReceivedRequestDTO(user_id="tester", session_id=sid, message="hello", **fields))


class TestTheToken:
    def sid(self, svc):
        return svc.start_session(StartSessionRequestDTO(user_id="tester", username="t")).session_id

    def test_default_needs_no_token(self, agent):
        svc = service(ScriptedLLM(**SCENARIOS["no_actions"]["llm"]), agent)
        assert ask(svc, self.sid(svc), profile="default").success

    def test_dynamics_needs_its_own_token_and_the_token_of_special_does_not_open_it(self, agent):
        svc = service(ScriptedLLM(**SCENARIOS["no_actions"]["llm"]), agent)
        sid = self.sid(svc)
        assert ask(svc, sid, profile="dynamics", token="dynamics-token").success
        assert ask(svc, sid, profile="dynamics", token="special-token").error_code == "INVALID_PROFILE"
        assert ask(svc, sid, profile="dynamics").error_code == "INVALID_PROFILE"

    def test_a_question_of_dynamics_is_answered_by_dynamics_and_not_by_special(self, agent):
        from test_flow_golden import TRIAGE
        from test_resume import CHECK, TRIAGE_ASKS, TRIAGE_OK, Script, _verdict
        llm = ScriptedLLM(overrides={TRIAGE: Script(TRIAGE_ASKS, TRIAGE_OK), CHECK: Script(_verdict("answered", "Ana"))})
        svc = service(llm, agent)
        sid = self.sid(svc)
        first = ask(svc, sid, profile="dynamics", token="dynamics-token")
        assert first.awaiting_user_input and first.pause_id
        wrong = ask(svc, sid, profile="special", token="special-token", pause_id=first.pause_id)
        assert wrong.error_code == "PROFILE_MISMATCH"
        assert ask(svc, sid, profile="dynamics", token="dynamics-token", pause_id=first.pause_id).success
