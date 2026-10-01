"""
conversation-flow never plans or parses a movement any more: motion-flow does that, and Brain sends what it
decided as `robot_context`. With a robot_context the conversation flow skips planning (there is nothing to plan,
only what the robot does to say). No real LLM or network is used.
"""
import json
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.orchestration.state.flow_state import FlowState
from application.orchestration.support.metrics import SessionMetrics
from application.orchestration.engine.pipeline import Pipeline
from application.orchestration.flows.conversation_flow import CONVERSATION_FLOW
from application.orchestration.support.schemas import load_schema_file
from application.service.message_flow_service import MessageFlowService
from application.service.session_service import SessionService
from application.system_prompts.advanced import LoadCapabilities, LoadSystemPrompt
from domain.value_objects.motion.movement import Movement
from domain.value_objects.motion.robot_context import RobotContext
from infrastructure.inbound.http.fastapi import SessionFastAPI
from test_flow_golden import ScriptedLLM

TRIAGE = "triage_specialist_phase1_response_format"
DRAFT = "draft_writer_phase7_response_format"
USER = {"user_id": "tester"}

MOVING = RobotContext(directives=(Movement("left", 90.0, "forward"), Movement("left", -90.0, "forward")))
REFUSED = RobotContext(rejected_reason="I cannot turn an arm more than 360 degrees in one movement.")

ASKING_TRIAGE = {
    "intent": {"primary": "task_execution", "secondary": [], "confidence": 0.9},
    "user_goal": {"summary": "move the arm", "expected_outcome": "the arm moves"},
    "task_category": {"domain": "operations", "type": "generation", "complexity": "low"},
    "next_step": {"ready_to_execute": False, "status": "awaiting_user_input",
                  "recommended_action": "ask_user_for_missing_information",
                  "blocking_reason": "the degrees are missing", "requested_user_input": ["How many degrees?"]},
}


@pytest.fixture(autouse=True)
def _project_cwd(monkeypatch):
    monkeypatch.chdir(PROJECT_ROOT)


def formats(llm):
    return [call["format"] for call in llm.calls]


def draft_input(llm) -> str:
    return next(call["user_message"] for call in llm.calls if call["format"] == DRAFT)


class TestConversationFlowWithARobotContext:
    def test_planning_and_action_execution_are_skipped(self):
        llm = ScriptedLLM()
        Pipeline(llm, [], SessionMetrics(), flow=CONVERSATION_FLOW).run("raise your left arm and lower it", robot_context=MOVING)
        assert formats(llm) == [TRIAGE, DRAFT, "editor_in_chief_phase8_response_format"]

    def test_the_writer_is_told_what_the_robot_does(self):
        llm = ScriptedLLM()
        Pipeline(llm, [], SessionMetrics(), flow=CONVERSATION_FLOW).run("raise your left arm and lower it", robot_context=MOVING)
        text = draft_input(llm)
        assert "robot_context" in text
        assert "'arm': 'left'" in text and "90.0" in text and "-90.0" in text

    def test_the_writer_is_told_why_the_robot_cannot(self):
        llm = ScriptedLLM()
        Pipeline(llm, [], SessionMetrics(), flow=CONVERSATION_FLOW).run("turn your arm ten times", robot_context=REFUSED)
        assert "I cannot turn an arm more than 360 degrees" in draft_input(llm)

    def test_triage_does_not_ask_again_what_motion_flow_already_handled(self):
        llm = ScriptedLLM({TRIAGE: ASKING_TRIAGE})
        result = Pipeline(llm, [], SessionMetrics(), flow=CONVERSATION_FLOW).run("move my arm", robot_context=MOVING)
        assert result.paused is None and result.reply == "final answer"

    def test_the_conversation_flow_returns_no_movements(self):
        llm = ScriptedLLM()
        assert Pipeline(llm, [], SessionMetrics(), flow=CONVERSATION_FLOW).run("move", robot_context=MOVING).movements == ()

    def test_without_a_robot_context_nothing_changes(self):
        llm = ScriptedLLM()
        Pipeline(llm, [], SessionMetrics(), flow=CONVERSATION_FLOW).run("what is the weather")
        assert "project_manager_phase2_response_format" in formats(llm)
        assert "robot_context" not in draft_input(llm)

    def test_the_state_keeps_the_context(self):
        assert FlowState(message="x").robot_context is None


class TestThroughTheService:
    def test_the_dto_becomes_the_domain_context(self):
        from application.inbound.dto.message import TextRequestDTO
        llm = ScriptedLLM()
        service = MessageFlowService(outbound_port=llm, mcp_list=[])
        request = TextRequestDTO(
            session_id="s", content="raise your arm",
            robot_context={"directives": [{"arm": "right", "degrees": 45, "direction": "reverse"}]}, **USER)
        service.text(request)
        assert "'arm': 'right'" in draft_input(llm)
        assert "reverse" in draft_input(llm)


class TestHttp:
    def _client(self, llm):
        app = FastAPI()
        SessionFastAPI(App=app, SessionPort=SessionService(outbound_port=llm, mcp_list=[]))
        client = TestClient(app)
        session_id = client.post("/session/start", json={"username": "t", **USER}).json()["data"]["session_id"]
        return client, session_id

    def test_the_route_accepts_a_robot_context(self):
        llm = ScriptedLLM()
        client, session_id = self._client(llm)
        body = client.post("/session/message", json={
            "session_id": session_id, "message": "raise your arm",
            "robot_context": {"directives": [{"arm": "left", "degrees": 90, "direction": "forward"}]}, **USER}).json()
        assert body["data"]["success"] is True
        assert DRAFT in formats(llm)
        assert "project_manager_phase2_response_format" not in formats(llm)

    def test_the_answer_of_conversation_flow_never_carries_a_directive(self):
        client, session_id = self._client(ScriptedLLM())
        data = client.post("/session/message", json={"session_id": session_id, "message": "hello", **USER}).json()["data"]
        assert data["directive"] is None

    def test_a_malformed_robot_context_is_refused(self):
        client, session_id = self._client(ScriptedLLM())
        response = client.post("/session/message", json={
            "session_id": session_id, "message": "x",
            "robot_context": {"directives": [{"arm": "middle", "degrees": 1}]}, **USER})
        assert response.status_code == 422


class TestNoMovementLeftInConversationFlow:
    def test_the_action_type_schema_has_no_robot_action(self):
        schema = load_schema_file("advanced/actions/actions.action_type.schema.json")
        assert "robot_action" not in schema["action_type"]["enum"]

    @pytest.mark.parametrize("phase", [2, 4])
    def test_the_prompts_do_not_plan_a_robot_action(self, phase):
        assert "robot_action" not in LoadSystemPrompt(phase)
        assert "arm=" not in LoadSystemPrompt(phase)

    def test_the_capabilities_no_longer_tell_the_agent_to_request_a_movement(self):
        text = LoadCapabilities()
        assert "robot_action" not in text and "REQUEST" not in text
        assert "move each of its arms independently" in text       # the robot can still do it, through another flow

    def test_the_project_manager_is_told_movements_are_not_its_job(self):
        assert "Never plan a movement" in LoadSystemPrompt(2)

    def test_the_writer_prompt_explains_the_robot_context(self):
        prompt = LoadSystemPrompt(7)
        assert "robot_context" in prompt and "never say that it is done" in prompt
