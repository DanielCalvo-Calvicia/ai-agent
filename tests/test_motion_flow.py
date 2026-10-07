"""
The movement flow: the motion planner (asks the user when a detail is missing, writes a short spoken line) and the
motion validator (plain code). It only decides: it returns an ordered list of movements. The identification flow
sends a message here when triage says task_category.domain = movement. No real LLM is used.
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

from application.orchestration.flows.movement import MOVEMENT_FLOW
from application.orchestration.flows.registry import FLOWS
from application.orchestration.flows.router import AgentRouter
from application.orchestration.support.metrics import SessionMetrics
from application.orchestration.support.model_selection import choose, load_config
from application.orchestration.phases.movement import motion_validator as validator
from application.orchestration.engine.pipeline import Pipeline
from application.service.session_service import SessionService
from application.system_prompts.general import build_system_prompt
from domain.value_objects.movement.movement import Movement
from infrastructure.inbound.http.fastapi import SessionFastAPI

from test_flow_golden import ScriptedLLM

TRIAGE = "triage_specialist_phase1_response_format"
PLANNER = "motion_planner_phase20_response_format"
USER = {"user_id": "tester"}

COMPLETE = {"ready_to_execute": True, "status": "complete", "recommended_action": "", "blocking_reason": "",
            "requested_user_input": []}
ASKING = {"ready_to_execute": False, "status": "awaiting_user_input",
          "recommended_action": "ask_user_for_missing_information",
          "blocking_reason": "the degrees are missing", "requested_user_input": ["How many degrees?"]}
# What triage says for a message that asks the robot to move: the domain sends it to the movement flow.
MOVEMENT_TRIAGE = {
    "intent": {"primary": "task_execution", "secondary": [], "confidence": 0.9},
    "user_goal": {"summary": "move an arm", "expected_outcome": "the arm moves"},
    "task_category": {"domain": "movement", "type": "orchestration", "complexity": "low"},
    "next_step": {"ready_to_execute": True, "status": "proceed", "recommended_action": "", "blocking_reason": "",
                  "requested_user_input": []},
}


@pytest.fixture(autouse=True)
def _project_cwd(monkeypatch):
    monkeypatch.chdir(PROJECT_ROOT)


def plan(*movements, is_motion_request=True, next_step=None, spoken_reply="Moving my arm."):
    """The answer of the planner: movements as (arm, degrees, direction) tuples."""
    return {
        "is_motion_request": is_motion_request,
        "movements": [{"arm": arm, "degrees": degrees, "direction": direction} for arm, degrees, direction in movements],
        "spoken_reply": spoken_reply,
        "next_step": next_step or COMPLETE,
    }


def scripted(planner, **overrides):
    """A scripted LLM whose triage sends the message to the movement flow."""
    return ScriptedLLM({TRIAGE: MOVEMENT_TRIAGE, PLANNER: planner, **overrides})


def run(llm, message="move", speak_movements=True, metrics=None):
    return AgentRouter(llm, [], metrics or SessionMetrics()).run(message, speak_movements=speak_movements)


class TestTheFlow:
    def test_the_steps_are_the_planner_and_the_validator(self):
        steps = [step.name for step in Pipeline(ScriptedLLM(), [], SessionMetrics(), flow=MOVEMENT_FLOW).steps]
        assert steps == ["motion_planner", "motion_validator"]

    def test_the_flow_is_registered(self):
        assert FLOWS.get("movement") is MOVEMENT_FLOW

    def test_one_movement(self):
        llm = scripted(plan(("left", 90, "forward"), spoken_reply="Turning my left arm."))
        result = run(llm, "raise your left arm a quarter turn")
        assert result.movements == (Movement("left", 90.0, "forward"),)
        assert result.flow == "movement"
        assert [call["format"] for call in llm.calls] == [TRIAGE, PLANNER]

    def test_a_sequence_keeps_its_order_and_the_sign_of_the_degrees(self):
        llm = scripted(plan(("left", 90, "forward"), ("left", -90, "forward")))
        assert run(llm, "left 90 and then left -90").movements == (
            Movement("left", 90.0, "forward"), Movement("left", -90.0, "forward"))

    def test_the_planner_has_its_own_prompt_and_triage_keeps_its_own(self):
        assert "You are the MOTION PLANNER" in build_system_prompt(20).content
        assert "You are the TRIAGE SPECIALIST" in build_system_prompt(1).content

    def test_nothing_is_planned_or_executed_like_in_the_special_flow(self):
        llm = scripted(plan(("right", 45, "forward")))
        run(llm)
        assert not any("project_manager" in call["format"] or "single_action" in call["format"] for call in llm.calls)

    def test_the_planner_reply_with_a_text_degrees_value_is_refused_not_crashed(self):
        result = run(scripted(plan(("left", "a lot", "forward"))))
        assert result.movements == () and result.reply == validator.NOT_A_NUMBER

    def test_the_planner_sees_what_triage_found_out_and_the_original_message(self):
        llm = scripted(plan(("left", 90, "forward")))
        run(llm, "turn the left arm a quarter turn")
        planner_call = [call for call in llm.calls if call["format"] == PLANNER][0]
        assert "turn the left arm a quarter turn" in planner_call["user_message"]


class TestWhatIsSaid:
    def test_a_movement_is_announced_with_the_planners_line(self):
        result = run(scripted(plan(("left", 90, "forward"), spoken_reply="Turning my left arm 90 degrees.")))
        assert result.reply == "Turning my left arm 90 degrees."

    def test_a_movement_is_silent_when_brain_says_not_to_speak_it(self):
        result = run(scripted(plan(("left", 90, "forward"), spoken_reply="Turning my left arm.")), speak_movements=False)
        assert result.movements == (Movement("left", 90.0, "forward"),) and result.reply == ""

    def test_a_refusal_is_always_said_even_when_movements_are_not_spoken(self):
        result = run(scripted(plan(("left", 9999, "forward"), spoken_reply="Sure!")), speak_movements=False)
        assert result.movements == () and result.reply == validator.TOO_FAR

    def test_a_message_that_is_not_a_movement_moves_nothing_and_says_the_planners_line(self):
        llm = scripted(plan(is_motion_request=False, spoken_reply="I can only move my two arms."))
        for speak in (True, False):
            result = run(llm, "can you dance?", speak_movements=speak)
            assert result.movements == () and result.reply == "I can only move my two arms."
            assert result.paused is None


class TestMissingDetails:
    def test_the_flow_asks_then_continues_with_the_answer(self):
        answers = iter([plan(is_motion_request=True, next_step=ASKING, spoken_reply=""),
                        plan(("left", 30, "forward"), spoken_reply="Turning my left arm 30 degrees.")])
        checker = {"verdict": "answered", "answer": "30 degrees, the left one", "message_to_user": ""}
        llm = scripted(lambda payload: next(answers), **{"answer_checker_phase9_response_format": checker})
        service = SessionService(outbound_port=llm, mcp_list=[])
        session_id = service.start_session(_start()).session_id

        first = service.message_received(_message(session_id, "move my arm"))
        assert first.success and first.response and first.movements == []     # the question to say out loud
        assert first.awaiting_user_input is True and first.flow == "movement"  # Brain speaks it and does not move

        second = service.message_received(_message(session_id, "30 degrees, the left one"))
        assert second.movements == [Movement("left", 30.0, "forward")]
        assert second.awaiting_user_input is False and second.response == "Turning my left arm 30 degrees."

        planner_calls = [call for call in llm.calls if call["format"] == PLANNER]
        assert len(planner_calls) == 2
        assert "30 degrees, the left one" in planner_calls[1]["user_message"]    # the planner saw the answer
        assert len([call for call in llm.calls if call["format"] == TRIAGE]) == 1  # the answer was not identified again

    def test_the_answer_uses_the_speak_setting_of_its_own_message(self):
        answers = iter([plan(next_step=ASKING, spoken_reply=""), plan(("left", 30, "forward"))])
        checker = {"verdict": "answered", "answer": "30", "message_to_user": ""}
        llm = scripted(lambda payload: next(answers), **{"answer_checker_phase9_response_format": checker})
        service = SessionService(outbound_port=llm, mcp_list=[])
        session_id = service.start_session(_start()).session_id

        service.message_received(_message(session_id, "move my arm", speak_movements=True))
        second = service.message_received(_message(session_id, "30", speak_movements=False))
        assert second.movements == [Movement("left", 30.0, "forward")] and second.response == ""

    def test_the_question_does_not_reach_the_validator(self):
        result = run(scripted(plan(next_step=ASKING)))
        assert result.paused is not None and result.movements == ()
        assert result.flow == "movement"


def _start():
    from application.inbound.dto.session import StartSessionRequestDTO
    return StartSessionRequestDTO(username="t", user_id="tester")


def _message(session_id, text, **extra):
    from application.inbound.dto.session import MessageReceivedRequestDTO
    return MessageReceivedRequestDTO(session_id=session_id, message=text, user_id="tester", **extra)


M = Movement


class TestValidator:
    @pytest.mark.parametrize("movements", [
        [M("left", 90.0, "forward")],
        [M("left", 90.0, "forward"), M("left", -90.0, "forward")],
        [M("right", 360.0, "forward")],
        [M("left", 45.0, "reverse"), M("right", 45.0, "reverse")],
        [M("left", 10.0, "forward")] * validator.MAX_MOVEMENTS,
    ])
    def test_a_good_sequence_passes(self, movements):
        assert validator.refusal_for(movements) is None

    @pytest.mark.parametrize("movements,reason", [
        ([], validator.NO_MOVEMENT_UNDERSTOOD),
        ([M("left", 10.0, "forward")] * (validator.MAX_MOVEMENTS + 1), validator.TOO_MANY_MOVEMENTS),
        ([M("middle", 90.0, "forward")], validator.UNKNOWN_ARM),
        ([M("left", 90.0, "sideways")], validator.UNKNOWN_DIRECTION),
        ([M("left", float("nan"), "forward")], validator.NOT_A_NUMBER),
        ([M("left", float("inf"), "forward")], validator.NOT_A_NUMBER),
        ([M("left", 0.0, "forward")], validator.ZERO_DEGREES),
        ([M("left", -90.0, "reverse")], validator.CONTRADICTORY),
        ([M("left", 361.0, "forward")], validator.TOO_FAR),
        ([M("left", -361.0, "forward")], validator.TOO_FAR),
        ([M("left", 360.0, "forward")] * 11, validator.TOO_MUCH_IN_TOTAL),
    ])
    def test_a_bad_sequence_is_refused_with_a_reason(self, movements, reason):
        assert validator.refusal_for(movements) == reason

    def test_one_bad_movement_refuses_the_whole_sequence(self):
        result = run(scripted(plan(("left", 90, "forward"), ("left", 9999, "forward"))))
        assert result.movements == ()                   # not even the good first movement is sent
        assert result.reply == validator.TOO_FAR

    def test_a_requested_movement_with_no_movements_is_refused(self):
        assert run(scripted(plan(is_motion_request=True))).reply == validator.NO_MOVEMENT_UNDERSTOOD

    def test_the_validator_makes_no_llm_call(self):
        llm = scripted(plan(("left", 90, "forward")))
        run(llm)
        assert len(llm.calls) == 2                      # triage and the planner, nothing else


class TestHttp:
    def _client(self, **extra):
        app = FastAPI()
        llm = scripted(plan(("left", 90, "forward"), ("left", -90, "forward"), spoken_reply="There and back."), **extra)
        SessionFastAPI(App=app, SessionPort=SessionService(outbound_port=llm, mcp_list=[]))
        return TestClient(app)

    def _session(self, client):
        return client.post("/session/start", json={"username": "t", **USER}).json()["data"]["session_id"]

    def test_the_route_answers_with_the_list_of_directives_and_the_flow(self):
        client = self._client()
        body = client.post("/session/message",
                           json={"session_id": self._session(client), "message": "there and back", **USER}).json()
        assert body["status"] == "success"
        assert body["data"]["directives"] == [
            {"arm": "left", "degrees": 90.0, "direction": "forward"},
            {"arm": "left", "degrees": -90.0, "direction": "forward"},
        ]
        assert body["data"]["success"] is True and body["data"]["response"] == "There and back."
        assert body["data"]["awaiting_user_input"] is False and body["data"]["flow"] == "movement"

    def test_speak_movements_false_leaves_the_response_empty(self):
        client = self._client()
        body = client.post("/session/message", json={"session_id": self._session(client), "message": "there and back",
                                                     "speak_movements": False, **USER}).json()
        assert body["data"]["response"] == "" and len(body["data"]["directives"]) == 2

    def test_a_movement_is_spoken_by_default(self):
        client = self._client()
        body = client.post("/session/message",
                           json={"session_id": self._session(client), "message": "x", **USER}).json()
        assert body["data"]["response"] == "There and back."


class TestModelAndMetrics:
    def test_the_planner_model_can_be_set_by_its_variable(self, monkeypatch):
        monkeypatch.setenv("AI_AGENT_MODEL_PHASE_20", "gpt-4.1-nano")
        assert choose(20) == ("gpt-4.1-nano", "env AI_AGENT_MODEL_PHASE_20")

    def test_the_planner_model_can_be_set_in_the_config_file_by_its_step_name(self, monkeypatch, tmp_path):
        config = tmp_path / "models.json"
        config.write_text(json.dumps({"steps": {"motion_planner": "gemini-2.5-flash"}}), encoding="utf-8")
        monkeypatch.setenv("AI_AGENT_MODELS_FILE", str(config))
        assert choose(20) == ("gemini-2.5-flash", "config steps")
        assert load_config()

    def test_the_planner_is_reported_under_its_name(self):
        metrics = SessionMetrics()
        metrics.begin_message("r1", "session", "hello")
        metrics.record(phase_id=20, model="m", prompt=1, completion=1, total=2)
        assert metrics.request_log[-1].phase_name == "motion_planner"
        assert "motion_planner" in metrics.by_phase

    def test_a_movement_run_is_tracked_under_the_planner_and_triage_names(self):
        metrics = SessionMetrics()
        run(scripted(plan(("left", 90, "forward"))), metrics=metrics)
        assert set(metrics.by_phase) == {"triage_specialist", "motion_planner"}
