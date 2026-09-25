"""
The movement path: a planned "robot_action" action, run through the real pipeline (scripted LLM,
no network), must come back as a typed RobotDirective on FlowResult and as data.directive on
/session/message. ai-agent never moves anything itself; this only checks what it hands off.
"""
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.inbound.dto.message import TextRequestDTO
from application.orchestration.robot_directive import RobotDirective, find_directive
from application.service.message_flow_service import MessageFlowService
from application.service.session_service import SessionService
from domain.entities.action import create_action
from infrastructure.inbound.http.fastapi import SessionFastAPI
from test_flow_golden import PM, ScriptedLLM, _action, _plan


@pytest.fixture(autouse=True)
def _project_cwd(monkeypatch):
    # Prompts, schemas and MCP configs are resolved relative to the working directory.
    monkeypatch.chdir(PROJECT_ROOT)
    monkeypatch.setattr("application.system_prompts.advanced.now_text", lambda: "Monday, 2026-01-05, 09:00 (UTC+00:00)")


# ===============================================
#  find_directive: pure unit tests
# ===============================================

class TestFindDirective:
    def test_no_actions(self):
        assert find_directive(None) is None
        assert find_directive([]) is None

    def test_successful_robot_action_is_parsed(self):
        action = create_action("1", "move", "robot_action", output_value="arm=left degrees=90 direction=forward")
        assert find_directive([action]) == RobotDirective(arm="left", degrees=90.0, direction="forward")

    def test_non_robot_action_is_ignored(self):
        action = create_action("1", "think", "analysis", output_value="arm=left degrees=90 direction=forward")
        assert find_directive([action]) is None

    def test_action_without_a_type_is_ignored(self):
        action = create_action("1", "think", output_value="something")
        assert find_directive([action]) is None

    def test_failed_robot_action_is_ignored(self):
        action = create_action("1", "move", "robot_action", error_value="could not decide")
        assert find_directive([action]) is None

    def test_malformed_output_is_ignored(self):
        action = create_action("1", "move", "robot_action", output_value="I moved the left arm")
        assert find_directive([action]) is None

    def test_reverse_direction_and_fractional_degrees(self):
        action = create_action("1", "move", "robot_action", output_value="arm=right degrees=12.5 direction=reverse")
        assert find_directive([action]) == RobotDirective(arm="right", degrees=12.5, direction="reverse")

    def test_found_inside_subactions_in_plan_order(self):
        child = create_action("1.1", "move", "robot_action", output_value="arm=left degrees=45 direction=forward")
        parent = create_action("1", "prepare", "analysis", output_value="ready")
        parent.subactions = {"1.1": child}
        other = create_action("2", "unrelated", "analysis", output_value="done")

        assert find_directive([parent, other]) == RobotDirective(arm="left", degrees=45.0, direction="forward")

    def test_first_match_wins(self):
        first = create_action("1", "move", "robot_action", output_value="arm=left degrees=10 direction=forward")
        second = create_action("2", "move", "robot_action", output_value="arm=right degrees=20 direction=reverse")

        assert find_directive([first, second]) == RobotDirective(arm="left", degrees=10.0, direction="forward")


# ===============================================
#  Full pipeline (scripted LLM, no network)
# ===============================================

def _robot_worker_output(_payload):
    return {"actions": [{"id": "1", "description": "d", "action_type": "robot_action",
                         "dependencies": [], "required_inputs": [], "error": "",
                         "mcp_context": {"server_id": "", "tool_name": "", "parameters": {}},
                         "output": "arm=left degrees=90 direction=forward"}]}


def _garbled_worker_output(_payload):
    return {"actions": [{"id": "1", "description": "d", "action_type": "robot_action",
                         "dependencies": [], "required_inputs": [], "error": "",
                         "mcp_context": {"server_id": "", "tool_name": "", "parameters": {}},
                         "output": "sure, moving the arm now"}]}


class TestPipelineDirective:
    def test_a_planned_robot_action_becomes_a_directive_on_the_result(self):
        llm = ScriptedLLM(overrides={
            PM: _plan(_action("1", "robot_action")),
            "phase4_single_action_response_format": _robot_worker_output,
        })
        service = MessageFlowService(outbound_port=llm, mcp_list=[])

        result = service.main_flow("move your left arm 90 degrees")

        assert result.directive == RobotDirective(arm="left", degrees=90.0, direction="forward")
        assert result.reply == "final answer"   # phase 8's default canned reply

    def test_a_plan_without_a_robot_action_has_no_directive(self):
        llm = ScriptedLLM(overrides={PM: _plan(_action("1", "analysis"))})
        service = MessageFlowService(outbound_port=llm, mcp_list=[])

        result = service.main_flow("what is the weather")

        assert result.directive is None

    def test_a_worker_that_ignores_the_required_format_yields_no_directive_but_still_replies(self):
        llm = ScriptedLLM(overrides={
            PM: _plan(_action("1", "robot_action")),
            "phase4_single_action_response_format": _garbled_worker_output,
        })
        service = MessageFlowService(outbound_port=llm, mcp_list=[])

        result = service.main_flow("move your left arm")

        assert result.directive is None
        assert result.reply == "final answer"


# ===============================================
#  HTTP: /session/message exposes data.directive
# ===============================================

def _client(llm) -> TestClient:
    app = FastAPI()
    SessionFastAPI(App=app, SessionPort=SessionService(outbound_port=llm, mcp_list=[]))
    return TestClient(app)


class TestHttpDirective:
    def test_message_response_carries_the_directive(self):
        llm = ScriptedLLM(overrides={
            PM: _plan(_action("1", "robot_action")),
            "phase4_single_action_response_format": _robot_worker_output,
        })
        client = _client(llm)
        session_id = client.post("/session/start", json={"user_id": "tester", "username": "t"}).json()["data"]["session_id"]

        response = client.post("/session/message", json={
            "user_id": "tester", "session_id": session_id, "message": "move your left arm 90 degrees",
        })
        body = response.json()

        assert response.status_code == 200
        assert body["data"]["success"] is True
        assert body["data"]["directive"] == {"arm": "left", "degrees": 90.0, "direction": "forward"}

    def test_message_response_has_no_directive_for_an_ordinary_reply(self):
        llm = ScriptedLLM(overrides={PM: _plan(_action("1", "analysis"))})
        client = _client(llm)
        session_id = client.post("/session/start", json={"user_id": "tester", "username": "t"}).json()["data"]["session_id"]

        response = client.post("/session/message", json={
            "user_id": "tester", "session_id": session_id, "message": "hello",
        })

        assert response.json()["data"]["directive"] is None
