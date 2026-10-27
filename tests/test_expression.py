# pyright: reportOptionalMemberAccess=false, reportArgumentType=false
"""
The arm gesture that goes with a spoken reply (the expression flow): the emotion of the exchange becomes random movements
that start with the speech and last about as long as it. No real LLM or network is used.
"""
import math
import os
import random
import statistics
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.inbound.dto.session import MessageReceivedResponseDTO
from application.orchestration.flows.expression import EXPRESSION_FLOW
from application.orchestration.flows.router import EXPRESSIVE_FLOWS, AgentRouter
from application.orchestration.phases.expression import emotion_reader, gesture_builder
from application.orchestration.phases.movement import motion_validator as validator
from application.orchestration.state.expression_state import ExpressionFlowState
from application.orchestration.state.paused_run import FlowResult
from application.orchestration.support import expression_settings
from application.orchestration.support.metrics import SessionMetrics
from domain.operations import gesture
from domain.operations.gesture import EMOTIONS, build_gesture, gesture_seconds, net_rotation
from domain.value_objects.movement.movement import Movement
from infrastructure.inbound.http.fastapi import message_data
from test_flow_golden import PM, TRIAGE, ScriptedLLM, _action, _plan
from test_router import PLANNER, PROCEED, formats, short, triage

EMOTION = "emotion_reader_phase30_response_format"
LIMITS = dict(max_movements=validator.MAX_MOVEMENTS, max_total_degrees=validator.MAX_TOTAL_ROTATION)


def make(emotion="joy", intensity=3, improvised=(), speech=10.0, seed=1, **limits):
    return build_gesture(emotion, intensity, list(improvised), speech, random.Random(seed), **{**LIMITS, **limits})


# ===============================================
#  THE GESTURE: RANDOM, SHAPED BY THE EMOTION, ABOUT AS LONG AS THE SPEECH
# ===============================================

class TestGestureBuilder:
    def test_the_same_seed_gives_the_same_gesture_and_another_seed_a_different_one(self):
        assert make(seed=7) == make(seed=7)
        assert len({tuple(make(seed=seed)) for seed in range(20)}) > 15

    def test_the_first_movement_starts_with_the_speech(self):
        assert all(make(seed=seed)[0].pause_seconds == 0.0 for seed in range(30))

    @pytest.mark.parametrize("emotion", EMOTIONS)
    @pytest.mark.parametrize("intensity", [1, 2, 3, 4, 5])
    def test_every_gesture_is_one_the_validator_accepts_and_leaves_every_arm_where_it_started(self, emotion, intensity):
        for seed in range(15):
            movements = make(emotion, intensity, seed=seed)
            assert movements and validator.refusal_for(movements) is None
            assert abs(net_rotation(movements, "left")) < 1 and abs(net_rotation(movements, "right")) < 1

    @pytest.mark.parametrize("speech", [1.0, 4.0, 10.0, 30.0])
    def test_it_lasts_about_as_long_as_the_speech(self, speech):
        # the target is the speech times a random 0.7 to 1.3; the way back is inside the budget
        target = max(gesture.MIN_TARGET_SECONDS, speech)
        ratios = [gesture_seconds(make(emotion, 3, speech=speech, seed=seed)) / target
                  for emotion in EMOTIONS for seed in range(25)]
        assert max(ratios) <= 1.35 and statistics.median(ratios) >= 0.75

    def test_a_long_speech_is_not_a_thirty_second_dance_for_ten_seconds_of_talking(self):
        durations = [gesture_seconds(make(speech=10.0, seed=seed)) for seed in range(60)]
        assert max(durations) < 14.0

    def test_even_a_one_word_reply_gets_a_small_gesture(self):
        assert all(make("calm", 1, speech=0.0, seed=seed) for seed in range(30))

    def test_the_emotion_shapes_the_randomness_without_dictating_the_gesture(self):
        def mean(emotion, attribute):
            return statistics.mean(attribute(m) for seed in range(150) for m in make(emotion, 3, seed=seed)[1:])

        assert mean("sadness", lambda m: m.pause_seconds) > 2 * mean("anger", lambda m: m.pause_seconds)
        assert mean("anger", lambda m: m.degrees) > 1.5 * mean("sadness", lambda m: m.degrees)
        assert len({tuple(make("anger", 3, seed=seed)) for seed in range(40)}) > 30     # still different every time

    def test_a_stronger_emotion_moves_the_arms_more(self):
        def mean_degrees(intensity):
            return statistics.mean(m.degrees for seed in range(150) for m in make("joy", intensity, seed=seed))

        assert mean_degrees(5) > 1.8 * mean_degrees(1)

    def test_an_unknown_emotion_or_intensity_does_not_break_it(self):
        assert make("bored", 9, seed=3)
        assert make("", 0, seed=3)

    def test_it_never_goes_over_the_limits_it_is_given(self):
        for seed in range(40):
            movements = make("anger", 5, speech=60.0, seed=seed, max_movements=6, max_total_degrees=500)
            assert len(movements) <= 6 and sum(m.degrees for m in movements) <= 500
            assert abs(net_rotation(movements, "left")) < 1 and abs(net_rotation(movements, "right")) < 1

    def test_every_movement_is_a_valid_one(self):
        for seed in range(40):
            for m in make("surprise", 5, speech=20.0, seed=seed):
                assert m.arm in ("left", "right") and m.direction in ("forward", "reverse")
                assert gesture.MIN_DEGREES <= m.degrees <= gesture.MAX_DEGREES and m.pause_seconds >= 0


class TestImprovisedMovements:
    def test_the_models_own_ideas_are_mixed_in_and_the_arm_still_comes_back(self):
        idea = Movement("left", 33.0, "forward")
        for seed in range(20):
            movements = make("joy", improvised=[idea], seed=seed)
            assert any(m.degrees == 33.0 and m.arm == "left" and m.direction == "forward" for m in movements)
            assert abs(net_rotation(movements, "left")) < 1 and abs(net_rotation(movements, "right")) < 1

    def test_a_movement_that_cannot_be_used_is_left_out(self):
        junk = [Movement("middle", 30.0, "forward"), Movement("left", float("nan"), "forward"),
                Movement("left", 0.0, "forward"), Movement("right", 30.0, "sideways")]
        with_junk = make("joy", improvised=junk, seed=5)
        assert with_junk == make("joy", seed=5)

    def test_a_huge_idea_is_cut_to_one_movement_of_at_most_360_degrees(self):
        movements = make("joy", improvised=[Movement("left", 5000.0, "forward")], speech=60.0, seed=2)
        assert max(m.degrees for m in movements) <= 360.0 and validator.refusal_for(movements) is None


# ===============================================
#  THE EMOTION READER READS WHAT THE MODEL ANSWERED, WHATEVER IT ANSWERED
# ===============================================

class Answer:
    def __init__(self, raw):
        self.raw = raw


class TestEmotionReaderPhase:
    def apply(self, raw):
        state = ExpressionFlowState(message="hi", reply="hello")
        emotion_reader.EMOTION_READER.apply(state, Answer(raw))
        return state

    def test_it_reads_the_emotion_the_intensity_and_the_ideas(self):
        state = self.apply({"emotion": "Sadness", "intensity": 4,
                            "improvised": [{"arm": "left", "degrees": 40, "direction": "reverse"}]})
        assert (state.emotion, state.intensity) == ("sadness", 4)
        assert state.improvised == [Movement("left", 40.0, "reverse")]

    @pytest.mark.parametrize("raw", [{}, {"emotion": "boredom", "intensity": 9, "improvised": "none"},
                                     {"emotion": None, "intensity": "very", "improvised": None}])
    def test_anything_it_cannot_use_becomes_calm_and_a_middle_intensity(self, raw):
        state = self.apply(raw)
        assert (state.emotion, state.intensity) == ("calm", 3) and state.improvised == []

    def test_at_most_three_ideas_are_taken(self):
        idea = {"arm": "left", "degrees": 10, "direction": "forward"}
        assert len(self.apply({"emotion": "joy", "intensity": 3, "improvised": [idea] * 7}).improvised) == 3

    def test_the_model_sees_what_the_user_said_and_what_the_robot_answers(self):
        state = ExpressionFlowState(message="I got a puppy!", reply="How wonderful!")
        text = emotion_reader.EMOTION_READER.build_input(state)
        assert "I got a puppy!" in text and "How wonderful!" in text

    def test_the_schema_asks_for_the_emotion_the_intensity_and_the_ideas(self):
        properties = emotion_reader.EMOTION_READER.properties()
        assert set(properties) == {"emotion", "intensity", "improvised"}
        assert properties["emotion"]["enum"] == list(EMOTIONS)
        assert properties["improvised"]["maxItems"] == 3

    def test_the_prompt_names_every_emotion_the_builder_knows(self):
        with open(os.path.join(PROJECT_ROOT, emotion_reader.PROMPT_FILE), encoding="utf-8") as f:
            prompt = f.read()
        assert all(emotion in prompt for emotion in EMOTIONS)


class TestSettings:
    def test_it_is_on_unless_switched_off(self, monkeypatch):
        monkeypatch.delenv("AI_AGENT_EXPRESSION", raising=False)
        assert expression_settings.expression_enabled() is True
        for off in ("0", "false", "No", "OFF"):
            monkeypatch.setenv("AI_AGENT_EXPRESSION", off)
            assert expression_settings.expression_enabled() is False

    def test_the_speech_length_comes_from_the_text_and_the_speaking_rate(self, monkeypatch):
        monkeypatch.delenv("AI_AGENT_SPEECH_CHARS_PER_SECOND", raising=False)
        assert expression_settings.speech_seconds("x" * 28) == pytest.approx(2.0)
        monkeypatch.setenv("AI_AGENT_SPEECH_CHARS_PER_SECOND", "7")
        assert expression_settings.speech_seconds("x" * 28) == pytest.approx(4.0)

    @pytest.mark.parametrize("bad", ["fast", "0", "-3"])
    def test_a_speaking_rate_that_makes_no_sense_falls_back_to_the_default(self, monkeypatch, bad):
        monkeypatch.setenv("AI_AGENT_SPEECH_CHARS_PER_SECOND", bad)
        assert expression_settings.chars_per_second() == expression_settings.DEFAULT_CHARS_PER_SECOND

    def test_a_seed_makes_the_gestures_repeatable(self):
        assert expression_settings.new_rng("5").random() == expression_settings.new_rng("5").random()
        assert expression_settings.new_rng("5").random() != expression_settings.new_rng("6").random()


# ===============================================
#  THE ROUTER GIVES A REPLY ITS GESTURE
# ===============================================

@pytest.fixture(autouse=True)
def _project_cwd(monkeypatch):
    monkeypatch.chdir(PROJECT_ROOT)
    monkeypatch.setattr("application.system_prompts.general.now_text", lambda: "Monday, 2026-01-05, 09:00 (UTC+00:00)")


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("AI_AGENT_EXPRESSION", "1")
    monkeypatch.setenv("AI_AGENT_EXPRESSION_SEED", "11")
    monkeypatch.setenv("AI_AGENT_MAX_ATTEMPTS", "1")


def route(llm, message="I just got a puppy!", **kwargs):
    return AgentRouter(llm, [], SessionMetrics()).run(message, **kwargs)


def feeling(emotion="joy", intensity=4, improvised=()):
    return {EMOTION: {"emotion": emotion, "intensity": intensity, "improvised": list(improvised)}}


class TestTheReplyGetsItsGesture:
    def test_a_conversation_reply_comes_with_a_gesture_made_after_the_reply_is_final(self, on):
        llm = ScriptedLLM(overrides={TRIAGE: triage("communication"), **feeling()})
        result = route(llm)
        assert [short(f) for f in formats(llm)] == [
            "triage_specialist_phase1", "draft_writer_phase7", "editor_in_chief_phase8", "emotion_reader_phase30"]
        assert result.reply == "final answer" and result.flow == "conversation"
        assert result.gesture is True and result.movements and result.movements[0].pause_seconds == 0.0

    def test_the_model_reads_the_exchange_the_user_and_the_final_reply(self, on):
        llm = ScriptedLLM(overrides={TRIAGE: triage("communication"), **feeling()})
        route(llm, "I just got a puppy!")
        asked = [call for call in llm.calls if call["format"] == EMOTION][0]["user_message"]
        assert "I just got a puppy!" in asked and "final answer" in asked

    def test_the_gesture_follows_the_length_of_the_reply(self, on, monkeypatch):
        reply = lambda payload: {"user_goal": {"summary": "s", "expected_outcome": "word " * 60},
                                 "next_step": {**PROCEED, "status": "complete"}}
        long = route(ScriptedLLM(overrides={TRIAGE: triage("communication"), **feeling(),
                                            "editor_in_chief_phase8_response_format": reply}))
        short_reply = route(ScriptedLLM(overrides={TRIAGE: triage("communication"), **feeling()}))
        assert gesture_seconds(long.movements) > gesture_seconds(short_reply.movements)

    def test_a_task_reply_gets_a_gesture_too(self, on):
        llm = ScriptedLLM(overrides={TRIAGE: triage("writing"), PM: _plan(_action("1", "generation")), **feeling("calm", 2)})
        result = route(llm, "make a table of my family")
        assert short(formats(llm)[-1]) == "emotion_reader_phase30" and result.flow == "special"
        assert result.gesture is True and result.movements

    def test_what_the_user_asked_to_move_gets_no_extra_gesture(self, on):
        llm = ScriptedLLM(overrides={TRIAGE: triage("movement"), PLANNER: {
            "is_motion_request": True, "movements": [{"arm": "left", "degrees": 90, "direction": "forward"}],
            "spoken_reply": "Turning my left arm.", "next_step": {**PROCEED, "status": "complete"}}})
        result = route(llm, "raise your left arm")
        assert not any("emotion_reader" in f for f in formats(llm))
        assert result.flow == "movement" and result.gesture is False
        assert [(m.arm, m.degrees, m.pause_seconds) for m in result.movements] == [("left", 90.0, 0.0)]

    def test_the_model_s_own_idea_is_in_the_gesture(self, on):
        idea = {"arm": "right", "degrees": 33, "direction": "forward"}
        llm = ScriptedLLM(overrides={TRIAGE: triage("communication"), **feeling("surprise", 5, [idea])})
        movements = route(llm).movements
        assert any(m.arm == "right" and m.degrees == 33.0 for m in movements)

    def test_a_model_that_answers_nonsense_still_gives_a_calm_gesture(self, on):
        llm = ScriptedLLM(overrides={TRIAGE: triage("communication"),
                                     EMOTION: {"emotion": "boredom", "intensity": 99, "improvised": "x"}})
        result = route(llm)
        assert result.gesture is True and result.movements

    def test_switched_off_there_is_no_model_call_and_no_gesture(self, on, monkeypatch):
        monkeypatch.setenv("AI_AGENT_EXPRESSION", "0")
        llm = ScriptedLLM(overrides={TRIAGE: triage("communication")})
        result = route(llm)
        assert not any("emotion_reader" in f for f in formats(llm))
        assert result.gesture is False and result.movements == ()


class TestTheReplyIsNeverHeldBack:
    def test_when_the_model_fails_the_reply_goes_out_without_a_gesture(self, on):
        def broken(payload):
            raise RuntimeError("provider down")

        llm = ScriptedLLM(overrides={TRIAGE: triage("communication"), EMOTION: broken})
        result = route(llm)
        assert result.reply == "final answer" and result.gesture is False and result.movements == ()

    def test_a_gesture_the_validator_refuses_is_dropped_and_the_reply_stays(self, on, monkeypatch):
        monkeypatch.setattr(gesture_builder, "build_gesture", lambda *args, **kwargs: [Movement("middle", 30.0)])
        llm = ScriptedLLM(overrides={TRIAGE: triage("communication"), **feeling()})
        result = route(llm)
        assert result.reply == "final answer" and result.gesture is False and result.movements == ()

    @pytest.mark.parametrize("result", [
        FlowResult(reply="  ", flow="conversation"),                                  # nothing to say
        FlowResult(reply="Okay.", flow="conversation", ended_early=True),              # the user cut it short
        FlowResult(reply="Turning.", flow="movement"),                                 # the user asked for movements
        FlowResult(reply="Which one?", flow="identification"),                         # triage asking a detail
        FlowResult(reply="Okay.", flow="conversation", movements=(Movement("left", 10.0),)),
    ])
    def test_these_get_no_gesture_and_no_model_call(self, on, result):
        llm = ScriptedLLM()
        router = AgentRouter(llm, [], SessionMetrics())
        assert router._with_gesture("hello", result) is result
        assert llm.calls == [] and result.gesture is False

    def test_only_the_conversation_and_special_flows_are_expressive(self):
        assert EXPRESSIVE_FLOWS == ("conversation", "special")

    def test_the_expression_flow_is_two_steps_the_reader_and_the_builder(self, on):
        from application.orchestration.engine.pipeline import Pipeline
        pipeline = Pipeline(ScriptedLLM(overrides=feeling()), [], SessionMetrics(), flow=EXPRESSION_FLOW)
        assert [step.name for step in pipeline.steps] == ["emotion_reader", "gesture_builder"]


# ===============================================
#  WHAT GOES OUT OVER HTTP
# ===============================================

class TestWhatBrainReceives:
    def test_a_gesture_goes_out_with_its_pauses_and_its_flag(self):
        answer = MessageReceivedResponseDTO(
            response="How wonderful!", success=True, flow="conversation", gesture=True,
            movements=[Movement("left", 60.0, "forward", 0.0), Movement("right", 45.0, "reverse", 0.8)])
        data = message_data(answer)
        assert data.gesture is True
        assert [(d.arm, d.degrees, d.direction, d.pause_seconds) for d in data.directives] == [
            ("left", 60.0, "forward", 0.0), ("right", 45.0, "reverse", 0.8)]

    def test_what_the_user_asked_for_is_not_flagged_as_a_gesture(self):
        data = message_data(MessageReceivedResponseDTO(
            response="Turning.", success=True, flow="movement", movements=[Movement("left", 90.0)]))
        assert data.gesture is False and data.directives[0].pause_seconds == 0.0
