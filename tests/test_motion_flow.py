"""
motion-flow: triage (shared), the motion planner (asks the user when a detail is missing) and the motion
validator (plain code). It only decides: it returns an ordered list of movements. No real LLM is used.
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

from application.orchestration.flows.registry import FLOWS
from application.orchestration.flows.motion_flow import MOTION_FLOW
from application.orchestration.support.metrics import SessionMetrics
from application.orchestration.support.model_selection import choose, load_config
from application.orchestration.phases.motion_flow import motion_validator as validator
from application.orchestration.engine.pipeline import Pipeline
from application.service.session_service import SessionService
from application.system_prompts.advanced import build_system_prompt
from domain.value_objects.motion.movement import Movement
from infrastructure.inbound.http.fastapi import SessionFastAPI, message_data_for

from test_flow_golden import ScriptedLLM

TRIAGE = "triage_specialist_phase1_response_format"
PLANNER = "motion_planner_phase20_response_format"
USER = {"user_id": "tester"}

COMPLETE = {"ready_to_execute": True, "status": "complete", "recommended_action": "", "blocking_reason": "",
            "requested_user_input": []}
ASKING = {"ready_to_execute": False, "status": "awaiting_user_input",
          "recommended_action": "ask_user_for_missing_information",
          "blocking_reason": "the degrees are missing", "requested_user_input": ["How many degrees?"]}


@pytest.fixture(autouse=True)
def _project_cwd(monkeypatch):
    monkeypatch.chdir(PROJECT_ROOT)


def plan(*movements, is_motion_request=True, next_step=None):
    """The answer of the planner: movements as (arm, degrees, direction) tuples."""
    return {
        "is_motion_request": is_motion_request,
        "movements": [{"arm": arm, "degrees": degrees, "direction": direction} for arm, degrees, direction in movements],
        "next_step": next_step or COMPLETE,
    }


def run(llm, message="move"):
    return Pipeline(llm, [], SessionMetrics(), flow=MOTION_FLOW).run(message)


class TestTheFlow:
    def test_the_steps_are_triage_planner_validator(self):
        steps = [step.name for step in Pipeline(ScriptedLLM(), [], SessionMetrics(), flow=MOTION_FLOW).steps]
        assert steps == ["triage_specialist", "motion_planner", "motion_validator"]

    def test_the_flow_is_registered(self):
        assert FLOWS.get("motion-flow") is MOTION_FLOW

    def test_one_movement(self):
        llm = ScriptedLLM({PLANNER: plan(("left", 90, "forward"))})
        result = run(llm, "raise your left arm a quarter turn")
        assert result.movements == (Movement("left", 90.0, "forward"),)
        assert result.reply == ""
        assert [call["format"] for call in llm.calls] == [TRIAGE, PLANNER]

    def test_a_sequence_keeps_its_order_and_the_sign_of_the_degrees(self):
        llm = ScriptedLLM({PLANNER: plan(("left", 90, "forward"), ("left", -90, "forward"))})
        assert run(llm, "left 90 and then left -90").movements == (
            Movement("left", 90.0, "forward"), Movement("left", -90.0, "forward"))

    def test_a_message_that_is_not_a_movement_moves_nothing_and_says_nothing(self):
        llm = ScriptedLLM({PLANNER: plan(is_motion_request=False)})
        result = run(llm, "what is the weather like?")
        assert result.movements == () and result.reply == "" and result.paused is None

    def test_the_planner_has_its_own_prompt_and_the_shared_triage_keeps_its_own(self):
        assert "You are the MOTION PLANNER" in build_system_prompt(20).content
        assert "You are the TRIAGE SPECIALIST" in build_system_prompt(1).content

    def test_nothing_is_planned_or_executed_like_in_conversation_flow(self):
        llm = ScriptedLLM({PLANNER: plan(("right", 45, "forward"))})
        run(llm)
        assert not any("project_manager" in call["format"] or "single_action" in call["format"] for call in llm.calls)

    def test_the_planner_reply_with_a_text_degrees_value_is_refused_not_crashed(self):
        llm = ScriptedLLM({PLANNER: plan(("left", "a lot", "forward"))})
        result = run(llm)
        assert result.movements == () and result.reply == validator.NOT_A_NUMBER


class TestMissingDetails:
    def test_the_flow_asks_then_continues_with_the_answer(self):
        answers = iter([plan(is_motion_request=True, next_step=ASKING), plan(("left", 30, "forward"))])
        checker = {"verdict": "answered", "answer": "30 degrees, the left one", "message_to_user": ""}
        llm = ScriptedLLM({PLANNER: lambda payload: next(answers),
                           "answer_checker_phase9_response_format": checker})
        service = SessionService(outbound_port=llm, mcp_list=[], flow=MOTION_FLOW)
        session_id = service.start_session(_start()).session_id

        first = service.message_received(_message(session_id, "move my arm"))
        assert first.success and first.response and first.movements == []     # the question to say out loud
        assert first.awaiting_user_input is True                              # Brain speaks it and does not move

        second = service.message_received(_message(session_id, "30 degrees, the left one"))
        assert second.movements == [Movement("left", 30.0, "forward")]
        assert second.awaiting_user_input is False

        planner_calls = [call for call in llm.calls if call["format"] == PLANNER]
        assert len(planner_calls) == 2
        assert "30 degrees, the left one" in planner_calls[1]["user_message"]    # the planner saw the answer

    def test_the_question_does_not_reach_the_validator(self):
        llm = ScriptedLLM({PLANNER: plan(next_step=ASKING)})
        result = run(llm)
        assert result.paused is not None and result.movements == ()


def _start():
    from application.inbound.dto.session import StartSessionRequestDTO
    return StartSessionRequestDTO(username="t", **USER)


def _message(session_id, text):
    from application.inbound.dto.session import MessageReceivedRequestDTO
    return MessageReceivedRequestDTO(session_id=session_id, message=text, **USER)


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
        ([M("left", 360.0, "forward")] * 5, validator.TOO_MUCH_IN_TOTAL),
    ])
    def test_a_bad_sequence_is_refused_with_a_reason(self, movements, reason):
        assert validator.refusal_for(movements) == reason

    def test_one_bad_movement_refuses_the_whole_sequence(self):
        llm = ScriptedLLM({PLANNER: plan(("left", 90, "forward"), ("left", 9999, "forward"))})
        result = run(llm)
        assert result.movements == ()                   # not even the good first movement is sent
        assert result.reply == validator.TOO_FAR

    def test_a_requested_movement_with_no_movements_is_refused(self):
        llm = ScriptedLLM({PLANNER: plan(is_motion_request=True)})
        assert run(llm).reply == validator.NO_MOVEMENT_UNDERSTOOD

    def test_the_validator_makes_no_llm_call(self):
        llm = ScriptedLLM({PLANNER: plan(("left", 90, "forward"))})
        run(llm)
        assert len(llm.calls) == 2                      # triage and the planner, nothing else


class TestHttp:
    def _client(self):
        app = FastAPI()
        llm = ScriptedLLM({PLANNER: plan(("left", 90, "forward"), ("left", -90, "forward"))})
        service = SessionService(outbound_port=llm, mcp_list=[], flow=MOTION_FLOW)
        SessionFastAPI(App=app, SessionPort=service, prefix="/motion-flow", tag="motion-flow",
                       include_health=False, message_to_data=message_data_for("motion-flow"))
        return TestClient(app)

    def test_the_route_answers_with_the_list_of_directives(self):
        client = self._client()
        started = client.post("/motion-flow/session/start", json={"username": "t", **USER})
        session_id = started.json()["data"]["session_id"]

        body = client.post("/motion-flow/session/message",
                           json={"session_id": session_id, "message": "there and back", **USER}).json()
        assert body["status"] == "success"
        assert body["data"]["directives"] == [
            {"arm": "left", "degrees": 90.0, "direction": "forward"},
            {"arm": "left", "degrees": -90.0, "direction": "forward"},
        ]
        assert body["data"]["success"] is True and body["data"]["response"] == ""
        assert body["data"]["awaiting_user_input"] is False

    def test_the_answer_carries_no_single_directive_field(self):
        client = self._client()
        session_id = client.post("/motion-flow/session/start", json={"username": "t", **USER}).json()["data"]["session_id"]
        data = client.post("/motion-flow/session/message",
                           json={"session_id": session_id, "message": "x", **USER}).json()["data"]
        assert "directive" not in data


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

    def test_a_motion_run_is_tracked_under_the_planner_and_triage_names(self):
        metrics = SessionMetrics()
        llm = ScriptedLLM({PLANNER: plan(("left", 90, "forward"))})
        Pipeline(llm, [], metrics, flow=MOTION_FLOW).run("move")
        assert set(metrics.by_phase) == {"triage_specialist", "motion_planner"}
