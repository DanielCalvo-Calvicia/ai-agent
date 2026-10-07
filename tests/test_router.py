# pyright: reportOptionalMemberAccess=false, reportOperatorIssue=false
"""
The router: every message is identified first (triage) and then answered by ONE flow, chosen by
task_category.domain: communication -> conversation, movement -> movement, anything else -> special.
The chosen flow starts from what identification found out (no second triage), and a flow that asked the user a
question is resumed by the next message without identifying it again. No real LLM or network is used.
"""
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.orchestration.flows.conversation import CONVERSATION_FLOW
from application.orchestration.flows.movement import MOVEMENT_FLOW
from application.orchestration.flows.router import AgentRouter, DEFAULT_FLOW, FLOW_BY_DOMAIN, flow_for
from application.orchestration.flows.special import SPECIAL_FLOW
from application.orchestration.state.flow_state import FlowState
from application.orchestration.support.metrics import SessionMetrics
from application.orchestration.support.schemas import load_schema_file
from application.system_prompts.general import LoadCapabilities, LoadSystemPrompt
from domain.value_objects.llm_response.intent.intent import create_intent
from domain.value_objects.llm_response.task_category.domain import Domains
from domain.value_objects.llm_response.task_category.task_category import create_task_category
from test_flow_golden import PM, TRIAGE, ScriptedLLM, _action, _plan
from test_resume import Conversation

PLANNER = "motion_planner_phase20_response_format"
CHECK = "answer_checker_phase9_response_format"
DRAFT = "draft_writer_phase7_response_format"
EDITOR = "editor_in_chief_phase8_response_format"
GATE = "safety_quality_gatekeeper_phase3_response_format"

PROCEED = {"ready_to_execute": True, "status": "proceed", "recommended_action": "", "blocking_reason": "",
           "requested_user_input": []}


def triage(domain, next_step=None, summary="the goal"):
    return {
        "intent": {"primary": "information_request", "secondary": [], "confidence": 0.9},
        "user_goal": {"summary": summary, "expected_outcome": "the outcome"},
        "task_category": {"domain": domain, "type": "generation", "complexity": "low"},
        "next_step": next_step or PROCEED,
    }


ASKING = {"ready_to_execute": False, "status": "awaiting_user_input",
          "recommended_action": "ask_user_for_missing_information", "blocking_reason": "unclear",
          "requested_user_input": ["What do you want me to do?"]}


@pytest.fixture(autouse=True)
def _project_cwd(monkeypatch):
    monkeypatch.chdir(PROJECT_ROOT)
    monkeypatch.setattr("application.system_prompts.general.now_text", lambda: "Monday, 2026-01-05, 09:00 (UTC+00:00)")


def formats(llm):
    return [call["format"] for call in llm.calls]


def short(name):
    return name.replace("_response_format", "")


def route(llm, message="hello", **kwargs):
    return AgentRouter(llm, [], SessionMetrics()).run(message, **kwargs)


# ===============================================
#  WHICH FLOW
# ===============================================

class TestTheDomainPicksTheFlow:
    def test_communication_goes_to_the_conversation_flow(self):
        assert FLOW_BY_DOMAIN["communication"] is CONVERSATION_FLOW

    def test_movement_goes_to_the_movement_flow(self):
        assert FLOW_BY_DOMAIN["movement"] is MOVEMENT_FLOW

    def test_every_other_domain_goes_to_the_special_flow(self):
        others = [d.value for d in Domains if d.value not in ("communication", "movement")]
        assert others and all(FLOW_BY_DOMAIN.get(domain, DEFAULT_FLOW) is SPECIAL_FLOW for domain in others)

    def test_the_domain_list_is_the_one_the_router_knows(self):
        assert {d.value for d in Domains} == {"software", "data", "writing", "design", "research",
                                              "operations", "communication", "system", "movement"}

    def test_a_state_without_a_task_category_goes_to_the_special_flow(self):
        assert flow_for(FlowState(message="hi")) is SPECIAL_FLOW

    def test_flow_for_reads_the_domain_of_the_state(self):
        state = FlowState(message="hi")
        state.intent = create_intent(primary="information_request", secondary=[], confidence=0.9)
        state.task_category = create_task_category(domain_value="communication", type_value="generation",
                                                   complexity_value="low")
        assert flow_for(state) is CONVERSATION_FLOW

    def test_the_schema_the_llm_sees_lists_movement_as_a_domain(self):
        schema = load_schema_file("general/task_category/task_category.domain.schema.json")
        assert "movement" in schema["domain"]["enum"]

    def test_the_triage_prompt_explains_what_each_domain_does(self):
        prompt = LoadSystemPrompt(1)
        assert '"communication"' in prompt and '"movement"' in prompt


class TestWhatEachFlowCalls:
    def test_communication_is_triage_then_two_writing_calls(self):
        llm = ScriptedLLM(overrides={TRIAGE: triage("communication")})
        result = route(llm, "hello there")
        assert [short(f) for f in formats(llm)] == [
            "triage_specialist_phase1", "draft_writer_phase7", "editor_in_chief_phase8"]
        assert result.reply == "final answer" and result.flow == "conversation"

    def test_a_task_goes_through_the_full_special_chain(self):
        llm = ScriptedLLM(overrides={TRIAGE: triage("writing"), PM: _plan(_action("1", "generation"))})
        result = route(llm, "make a table of my family")
        names = [short(f) for f in formats(llm)]
        assert names[0] == "triage_specialist_phase1" and names[1] == "project_manager_phase2"
        assert "safety_quality_gatekeeper_phase3" in names and names[-2:] == ["draft_writer_phase7", "editor_in_chief_phase8"]
        assert result.reply == "final answer" and result.flow == "special"

    def test_movement_is_triage_then_the_planner(self):
        llm = ScriptedLLM(overrides={TRIAGE: triage("movement"), PLANNER: {
            "is_motion_request": True, "movements": [{"arm": "left", "degrees": 90, "direction": "forward"}],
            "spoken_reply": "Turning my left arm.",
            "next_step": {**PROCEED, "status": "complete"}}})
        result = route(llm, "raise your left arm")
        assert [short(f) for f in formats(llm)] == ["triage_specialist_phase1", "motion_planner_phase20"]
        assert result.flow == "movement" and len(result.movements) == 1

    def test_the_conversation_flow_never_plans_or_moves(self):
        llm = ScriptedLLM(overrides={TRIAGE: triage("communication")})
        result = route(llm)
        assert not any("project_manager" in f or "single_action" in f or "motion" in f for f in formats(llm))
        assert result.movements == ()

    def test_a_movement_message_never_reaches_conversation_or_special(self):
        llm = ScriptedLLM(overrides={TRIAGE: triage("movement"), PLANNER: {
            "is_motion_request": False, "movements": [], "spoken_reply": "I can only move my arms.",
            "next_step": {**PROCEED, "status": "complete"}}})
        route(llm, "dance")
        assert DRAFT not in formats(llm) and PM not in formats(llm)


class TestWhatIdentificationHandsOver:
    def test_the_flow_starts_from_the_triage_so_nothing_is_classified_twice(self):
        llm = ScriptedLLM(overrides={TRIAGE: triage("communication")})
        route(llm)
        assert formats(llm).count(TRIAGE) == 1

    def test_the_writer_sees_the_goal_triage_found(self):
        llm = ScriptedLLM(overrides={TRIAGE: triage("communication", summary="greet the user")})
        route(llm, "hello")
        draft_call = [call for call in llm.calls if call["format"] == DRAFT][0]
        assert "greet the user" in draft_call["user_message"]

    def test_the_conversation_history_reaches_the_flow(self):
        from domain.value_objects.llm_request.message import Message, Role
        llm = ScriptedLLM(overrides={TRIAGE: triage("movement"), PLANNER: {
            "is_motion_request": True, "movements": [{"arm": "left", "degrees": 90, "direction": "forward"}],
            "spoken_reply": "", "next_step": {**PROCEED, "status": "complete"}}})
        route(llm, "and back", history=[Message(Role.USER, "left arm 90"), Message(Role.ASSISTANT, "ok")])
        planner_call = [call for call in llm.calls if call["format"] == PLANNER][0]
        assert "left arm 90" in planner_call["user_message"]


# ===============================================
#  A QUESTION IN THE MIDDLE
# ===============================================

class TestAQuestionInTheMiddle:
    def test_identification_can_ask_and_the_answer_is_identified_then_routed(self):
        triages = iter([triage("system", next_step=ASKING), triage("communication")])
        llm = ScriptedLLM(overrides={TRIAGE: lambda payload: next(triages),
                                     CHECK: {"verdict": "answered", "answer": "say hi", "message_to_user": ""}})
        conversation = Conversation(llm)

        first = conversation.say("do the thing")
        assert first.awaiting_user_input is True and first.flow == "identification"
        assert conversation.paused.flow == "identification"
        assert DRAFT not in formats(llm)                                  # no flow answered yet

        second = conversation.say("say hi")
        assert second.response == "final answer" and second.flow == "conversation"
        assert [short(f) for f in formats(llm)] == [
            "triage_specialist_phase1", "<text>", "answer_checker_phase9", "triage_specialist_phase1",
            "draft_writer_phase7", "editor_in_chief_phase8"]

    def test_stopping_while_identification_asks_ends_the_run_without_a_flow(self):
        llm = ScriptedLLM(overrides={TRIAGE: triage("system", next_step=ASKING),
                                     CHECK: {"verdict": "stop", "answer": "", "message_to_user": ""}})
        conversation = Conversation(llm)
        conversation.say("do the thing")
        result = conversation.say("forget it")
        assert result.success and result.awaiting_user_input is False and conversation.paused is None
        assert DRAFT not in formats(llm) and PM not in formats(llm)

    def test_a_special_flow_that_asks_is_resumed_without_identifying_again(self):
        plans = iter([
            {**_plan(_action("1", required_inputs=["recipient"])),
             "next_step": {"ready_to_execute": False, "status": "awaiting_user_input", "recommended_action": "",
                           "blocking_reason": "no recipient", "requested_user_input": ["Who is the recipient?"]}},
            _plan(_action("1"))])
        llm = ScriptedLLM(overrides={TRIAGE: triage("writing"), PM: lambda payload: next(plans),
                                     CHECK: {"verdict": "answered", "answer": "Bob", "message_to_user": ""}})
        conversation = Conversation(llm)

        first = conversation.say("write a note")
        assert first.awaiting_user_input is True and conversation.paused.flow == "special"

        second = conversation.say("Bob")
        assert second.awaiting_user_input is False and second.flow == "special"
        assert formats(llm).count(TRIAGE) == 1                            # the answer was not identified again

    def test_a_movement_question_is_answered_inside_the_movement_flow_even_if_the_words_sound_like_chat(self):
        triages = iter([triage("movement"), triage("communication")])
        llm = ScriptedLLM(overrides={
            TRIAGE: lambda payload: next(triages),
            PLANNER: lambda payload: {
                "is_motion_request": True, "movements": [], "spoken_reply": "",
                "next_step": {**ASKING, "requested_user_input": ["How many degrees?"]}},
            CHECK: {"verdict": "answered", "answer": "hello", "message_to_user": ""}})
        conversation = Conversation(llm)
        first = conversation.say("move")
        assert first.flow == "movement" and conversation.paused.flow == "movement"
        conversation.say("hello")
        assert DRAFT not in formats(llm)                                   # still the movement flow, not conversation
        assert formats(llm).count(TRIAGE) == 1


# ===============================================
#  NO MOVEMENT LEFT IN THE TEXT FLOWS
# ===============================================

class TestNoMovementLeftInTheTextFlows:
    def test_the_action_type_schema_has_no_robot_action(self):
        schema = load_schema_file("general/actions/actions.action_type.schema.json")
        assert "robot_action" not in schema["action_type"]["enum"]

    @pytest.mark.parametrize("phase", [2, 4])
    def test_the_prompts_do_not_plan_a_robot_action(self, phase):
        assert "robot_action" not in LoadSystemPrompt(phase)
        assert "arm=" not in LoadSystemPrompt(phase)

    def test_the_capabilities_no_longer_tell_the_agent_to_request_a_movement(self):
        text = LoadCapabilities()
        assert "robot_action" not in text and "REQUEST" not in text
        assert "move each of its arms independently" in text       # the robot can still do it, through the movement flow

    def test_the_project_manager_is_told_movements_are_not_its_job(self):
        assert "Never plan a movement" in LoadSystemPrompt(2)

    def test_the_writer_prompt_knows_nothing_about_a_robot_context(self):
        assert "robot_context" not in LoadSystemPrompt(7)
