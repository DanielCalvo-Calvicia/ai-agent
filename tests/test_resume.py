"""
Pause and resume: the flow stops to ask the user, the next message is checked as the answer,
and the flow continues from the step that was waiting (nothing is planned again).
"""
import os
import sys
from typing import Dict, List, Optional

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.inbound.dto.session import MessageReceivedRequestDTO, StartSessionRequestDTO
from application.orchestration.engine.answer_check import AnswerChecker, Check, FALLBACK_MESSAGE
from application.orchestration.state.paused_run import CONFIRMATION, INPUT
from application.orchestration.engine.pipeline import DECLINED_TEXT, STOPPED_TEXT
from application.service.session_service import SessionService

from test_flow_golden import GATE, PM, TRIAGE, ScriptedLLM, _action, _plan

CHECK = "answer_checker_phase9_response_format"

TRIAGE_ASKS = {
    "intent": {"primary": "task_execution", "secondary": [], "confidence": 0.9},
    "user_goal": {"summary": "a table of the family", "expected_outcome": "a table"},
    "task_category": {"domain": "writing", "type": "generation", "complexity": "low"},
    "next_step": {"ready_to_execute": False, "status": "awaiting_user_input",
                  "recommended_action": "ask_user_for_missing_information",
                  "blocking_reason": "the names are missing",
                  "requested_user_input": ["What are the names of your four family members?"]},
}

TRIAGE_OK = {
    "intent": {"primary": "task_execution", "secondary": [], "confidence": 0.9},
    "user_goal": {"summary": "a table of the family", "expected_outcome": "a table"},
    "task_category": {"domain": "writing", "type": "generation", "complexity": "low"},
    "next_step": {"ready_to_execute": True, "status": "proceed", "recommended_action": "",
                  "blocking_reason": "", "requested_user_input": []},
}

GATE_CONFIRM = {
    "safety_and_validation": {"sensitive": True, "requires_confirmation": True},
    "next_step": {"ready_to_execute": False, "status": "awaiting_confirmation",
                  "recommended_action": "confirm the change", "blocking_reason": "it changes something",
                  "requested_user_input": []},
}

GATE_OK = {
    "safety_and_validation": {"sensitive": False, "requires_confirmation": False},
    "next_step": {"ready_to_execute": True, "status": "proceed", "recommended_action": "",
                  "blocking_reason": "", "requested_user_input": []},
}


class Script:
    """Answers of one phase, one per call. The last one repeats."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), 0

    def __call__(self, payload):
        answer = self.answers[min(self.calls, len(self.answers) - 1)]
        self.calls += 1
        return answer


def _verdict(verdict, answer="", message=""):
    return {"verdict": verdict, "answer": answer, "message_to_user": message}


@pytest.fixture(autouse=True)
def _project_cwd(monkeypatch):
    monkeypatch.chdir(PROJECT_ROOT)


class Conversation:
    def __init__(self, llm: ScriptedLLM):
        self.llm = llm
        self.service = SessionService(outbound_port=llm, mcp_list=[])
        self.session_id = self.service.start_session(StartSessionRequestDTO(user_id="tester", username="t")).session_id

    def say(self, text):
        return self.service.message_received(
            MessageReceivedRequestDTO(user_id="tester", session_id=self.session_id, message=text))

    @property
    def paused(self):
        return self.service.sessions[self.session_id].paused

    def formats(self, start=0) -> List[str]:
        return [c["format"].split("_response")[0].replace("_single_action", "") for c in self.llm.calls[start:]]

    def input_of(self, format_prefix, nth=0) -> str:
        return [c for c in self.llm.calls if c["format"].startswith(format_prefix)][nth]["user_message"]


# ===============================================
#  A QUESTION THAT IS ANSWERED
# ===============================================

class TestAnsweredQuestion:
    def _ask_family_table(self, **overrides):
        llm = ScriptedLLM(overrides={TRIAGE: Script(TRIAGE_ASKS, TRIAGE_OK), CHECK: Script(_verdict(
            "answered", "The family members are Ana, Luis, Pepe and Mia")), **overrides})
        conversation = Conversation(llm)
        first = conversation.say("My family has 4 people. Make a table with each name.")
        return conversation, first

    def test_the_first_message_asks_and_waits(self):
        conversation, first = self._ask_family_table()
        assert first.success and first.response == "Please tell me the missing details."
        assert conversation.paused is not None and conversation.paused.kind == INPUT
        assert conversation.paused.step_index == 0
        assert conversation.paused.requested_items == ["What are the names of your four family members?"]

    def test_a_correct_answer_continues_and_does_not_plan_again_from_the_start(self):
        conversation, _ = self._ask_family_table()
        before = len(conversation.llm.calls)
        second = conversation.say("Ana, Luis, Pepe and Mia")

        assert second.success and second.response == "final answer"
        assert conversation.paused is None
        # the answer is checked, then triage runs again WITH the answer, then the rest of the chain
        assert conversation.formats(before)[:3] == ["answer_checker_phase9", "triage_specialist_phase1", "project_manager_phase2"]
        assert conversation.formats(before)[-2:] == ["draft_writer_phase7", "editor_in_chief_phase8"]

    def test_the_step_that_waited_gets_the_answer_and_the_original_request(self):
        conversation, _ = self._ask_family_table()
        conversation.say("Ana, Luis, Pepe and Mia")
        rerun = conversation.input_of("triage", 1)
        assert "My family has 4 people. Make a table with each name." in rerun
        assert "Information the user gave when asked:" in rerun
        assert "The family members are Ana, Luis, Pepe and Mia" in rerun

    def test_the_planner_receives_the_answers_too(self):
        conversation, _ = self._ask_family_table()
        conversation.say("Ana, Luis, Pepe and Mia")
        assert "'user_answers': [{'question':" in conversation.input_of("project_manager")
        assert "The family members are Ana, Luis, Pepe and Mia" in conversation.input_of("project_manager")

    def test_the_answer_checker_sees_the_question_the_items_and_the_reply(self):
        conversation, _ = self._ask_family_table()
        conversation.say("Ana, Luis, Pepe and Mia")
        checker_input = conversation.input_of("answer_checker")
        assert "'kind': 'input'" in checker_input
        assert "What are the names of your four family members?" in checker_input
        assert "'user_reply': 'Ana, Luis, Pepe and Mia'" in checker_input
        assert "My family has 4 people" in checker_input

    def test_the_whole_conversation_is_remembered(self):
        conversation, _ = self._ask_family_table()
        conversation.say("Ana, Luis, Pepe and Mia")
        history = [m.content for m in conversation.service.sessions[conversation.session_id].history]
        assert history[0].startswith("My family has 4 people")
        assert "Ana, Luis, Pepe and Mia" in history
        assert history[-1] == "final answer"

    def test_a_plan_that_needs_input_resumes_at_the_planner_not_at_triage(self):
        llm = ScriptedLLM(overrides={
            PM: Script(
                {"actions": [_action("1", required_inputs=["recipient"])], "task_category_complexity": "low",
                 "next_step": {"ready_to_execute": False, "status": "awaiting_user_input",
                               "recommended_action": "", "blocking_reason": "no recipient",
                               "requested_user_input": ["Who is the recipient?"]}},
                _plan(_action("1"))),
        })
        conversation = Conversation(llm)
        conversation.say("Write a note")
        assert conversation.paused.step_index == 1
        before = len(llm.calls)
        conversation.say("Bob")
        assert conversation.formats(before) == [
            "answer_checker_phase9", "project_manager_phase2", "safety_quality_gatekeeper_phase3", "phase4",
            "draft_writer_phase7", "editor_in_chief_phase8"]                 # triage did not run again

    def test_it_can_ask_again_after_the_answer(self):
        llm = ScriptedLLM(overrides={TRIAGE: Script(TRIAGE_ASKS), CHECK: Script(_verdict("answered", "Ana"))})
        conversation = Conversation(llm)
        conversation.say("Make a table")
        second = conversation.say("Ana")
        assert second.response == "Please tell me the missing details."      # triage still is not satisfied
        assert conversation.paused is not None


# ===============================================
#  A REPLY THAT DOES NOT ANSWER
# ===============================================

class TestNotAnswered:
    def _waiting(self, *verdicts):
        llm = ScriptedLLM(overrides={TRIAGE: Script(TRIAGE_ASKS, TRIAGE_OK), CHECK: Script(*verdicts)})
        conversation = Conversation(llm)
        conversation.say("Make a table of my family")
        return conversation

    def test_the_user_is_asked_again_and_the_flow_keeps_waiting(self):
        conversation = self._waiting(_verdict("not_answered", message="I still need the four names."))
        before = len(conversation.llm.calls)
        reply = conversation.say("what is the weather?")
        assert reply.success and reply.response == "I still need the four names."
        assert conversation.formats(before) == ["answer_checker_phase9"]     # nothing else ran
        assert conversation.paused is not None

    def test_it_keeps_asking_until_the_user_answers(self):
        conversation = self._waiting(
            _verdict("not_answered", message="I still need the names."),
            _verdict("not_answered", message="Please give me the four names."),
            _verdict("answered", "Ana, Luis, Pepe, Mia"))
        assert conversation.say("hmm").response == "I still need the names."
        assert conversation.say("no idea").response == "Please give me the four names."
        assert conversation.paused is not None
        assert conversation.say("Ana, Luis, Pepe, Mia").response == "final answer"
        assert conversation.paused is None

    def test_a_reply_without_a_message_gets_a_default_one(self):
        conversation = self._waiting(_verdict("not_answered"))
        assert conversation.say("hmm").response == FALLBACK_MESSAGE

    def test_an_unknown_verdict_is_a_reply_that_does_not_answer(self):
        conversation = self._waiting(_verdict("banana"))
        reply = conversation.say("hmm")
        assert reply.response == FALLBACK_MESSAGE and conversation.paused is not None

    def test_a_yes_to_a_question_for_information_is_not_an_answer(self):
        conversation = self._waiting(_verdict("declined"))
        assert conversation.say("no").response == FALLBACK_MESSAGE
        assert conversation.paused is not None


# ===============================================
#  STOP AND RESTART
# ===============================================

class TestStop:
    def test_an_explicit_stop_forgets_the_question(self):
        llm = ScriptedLLM(overrides={TRIAGE: Script(TRIAGE_ASKS, TRIAGE_OK), CHECK: Script(_verdict("stop"))})
        conversation = Conversation(llm)
        conversation.say("Make a table of my family")
        reply = conversation.say("forget it, stop")
        assert reply.success and reply.response == STOPPED_TEXT
        assert conversation.paused is None

    def test_after_a_stop_the_next_message_is_a_new_request(self):
        llm = ScriptedLLM(overrides={TRIAGE: Script(TRIAGE_ASKS, TRIAGE_OK), CHECK: Script(_verdict("stop"))})
        conversation = Conversation(llm)
        conversation.say("Make a table of my family")
        conversation.say("stop")
        before = len(llm.calls)
        reply = conversation.say("What is 2+2?")
        assert reply.response == "final answer"
        assert conversation.formats(before)[0] == "triage_specialist_phase1"    # not checked as an answer
        assert conversation.input_of("triage", 1).startswith("Conversation so far:")   # but the history is there


# ===============================================
#  CONFIRMATION
# ===============================================

class TestConfirmation:
    def _waiting_for_confirmation(self, *verdicts):
        llm = ScriptedLLM(overrides={
            GATE: Script(GATE_CONFIRM),
            PM: _plan(_action("1"), _action("2", "mcp_tool_call", dependencies=["1"])),
            CHECK: Script(*verdicts),
        })
        conversation = Conversation(llm)
        conversation.say("Change my settings")
        return conversation

    def test_the_run_waits_for_a_yes_or_a_no(self):
        conversation = self._waiting_for_confirmation(_verdict("confirmed"))
        assert conversation.paused.kind == CONFIRMATION
        assert conversation.paused.step_index == 2                       # the safety gate

    def test_a_yes_continues_after_the_gate_without_planning_or_checking_again(self):
        conversation = self._waiting_for_confirmation(_verdict("confirmed"))
        before = len(conversation.llm.calls)
        reply = conversation.say("yes, go ahead")
        assert reply.response == "final answer" and conversation.paused is None
        assert conversation.formats(before) == [
            "answer_checker_phase9", "phase4", "phase5", "phase6", "draft_writer_phase7", "editor_in_chief_phase8"]

    def test_after_a_yes_the_mcp_action_is_no_longer_blocked(self):
        conversation = self._waiting_for_confirmation(_verdict("confirmed"))
        conversation.say("yes")
        mcp_input = conversation.input_of("phase5")
        assert "requires_confirmation=RequiresConfirmation(value=False)" in mcp_input

    def test_a_no_cancels_the_run(self):
        conversation = self._waiting_for_confirmation(_verdict("declined"))
        before = len(conversation.llm.calls)
        reply = conversation.say("no")
        assert reply.success and reply.response == DECLINED_TEXT
        assert conversation.paused is None
        assert conversation.formats(before) == ["answer_checker_phase9"]

    def test_a_reply_that_is_not_a_yes_or_a_no_is_asked_again(self):
        conversation = self._waiting_for_confirmation(
            _verdict("not_answered", message="Please answer yes or no."), _verdict("confirmed"))
        assert conversation.say("maybe?").response == "Please answer yes or no."
        assert conversation.paused.kind == CONFIRMATION
        assert conversation.say("yes").response == "final answer"

    def test_an_answered_verdict_to_a_confirmation_counts_as_a_yes(self):
        conversation = self._waiting_for_confirmation(_verdict("answered", "yes"))
        assert conversation.say("sure").response == "final answer"

    def test_a_stop_cancels_it_too(self):
        conversation = self._waiting_for_confirmation(_verdict("stop"))
        assert conversation.say("cancel everything").response == STOPPED_TEXT
        assert conversation.paused is None


# ===============================================
#  SESSIONS AND FAILURES
# ===============================================

class TestSessions:
    def test_each_session_keeps_its_own_waiting_run(self):
        llm = ScriptedLLM(overrides={TRIAGE: Script(TRIAGE_ASKS, TRIAGE_OK), CHECK: Script(_verdict("answered", "x"))})
        service = SessionService(outbound_port=llm, mcp_list=[])
        a = service.start_session(StartSessionRequestDTO(user_id="tester", username="a")).session_id
        b = service.start_session(StartSessionRequestDTO(user_id="tester", username="b")).session_id
        service.message_received(MessageReceivedRequestDTO(user_id="tester", session_id=a, message="Make a table"))
        assert service.sessions[a].paused is not None and service.sessions[b].paused is None

    def test_a_failure_while_checking_keeps_the_question_waiting(self):
        class Flaky(ScriptedLLM):
            fail = False

            def ask(self, Payload):
                if Flaky.fail and Payload.response_format and Payload.response_format.name == CHECK:
                    raise ConnectionError("down")
                return super().ask(Payload)

        llm = Flaky(overrides={TRIAGE: Script(TRIAGE_ASKS, TRIAGE_OK), CHECK: Script(_verdict("answered", "x"))})
        conversation = Conversation(llm)
        conversation.say("Make a table")
        Flaky.fail = True
        try:
            failed = conversation.say("Ana, Luis, Pepe, Mia")
        finally:
            Flaky.fail = False
        assert failed.success is False and "while reading your answer" in failed.response
        assert conversation.paused is not None                              # the question is still there
        assert conversation.say("Ana, Luis, Pepe, Mia").response == "final answer"


# ===============================================
#  ANSWER CHECKER, ALONE
# ===============================================

class TestVerdictFitting:
    @pytest.mark.parametrize("kind,check,expected", [
        (INPUT, Check("answered", "a"), "answered"),
        (INPUT, Check("confirmed"), "answered"),
        (INPUT, Check("declined"), "not_answered"),
        (INPUT, Check("stop"), "stop"),
        (INPUT, Check("nonsense"), "not_answered"),
        (CONFIRMATION, Check("answered"), "confirmed"),
        (CONFIRMATION, Check("confirmed"), "confirmed"),
        (CONFIRMATION, Check("declined"), "declined"),
        (CONFIRMATION, Check("stop"), "stop"),
        (CONFIRMATION, Check("not_answered", message="again"), "not_answered"),
    ])
    def test_a_verdict_always_fits_the_kind_of_question(self, kind, check, expected):
        assert AnswerChecker._fit(kind, check).verdict == expected


# ===============================================
#  THE PROMPTS THE PHASES SEE
# ===============================================

class TestContextOfEveryPhase:
    def test_every_phase_knows_what_the_robot_can_do_and_the_date(self):
        llm = ScriptedLLM()
        conversation = Conversation(llm)
        conversation.say("hello")
        assert llm.calls
        # the recorded calls carry only a hash of the system prompt, so read what is built for each phase
        from application.system_prompts.advanced import build_system_prompt
        for phase in range(1, 10):
            text = build_system_prompt(phase, clock=lambda: "Monday, 2026-01-05, 09:00 (UTC+00:00)").content
            assert "move each of its arms independently" in text
            assert "CURRENT DATE AND TIME: Monday, 2026-01-05, 09:00 (UTC+00:00)" in text

    def test_the_capabilities_come_before_the_phase_prompt(self):
        from application.system_prompts.advanced import build_system_prompt
        text = build_system_prompt(1, clock=lambda: "now").content
        assert text.index("WHO YOU SERVE") < text.index("You are the TRIAGE SPECIALIST")

    def test_the_clock_text_has_a_weekday_a_date_and_an_offset(self):
        import re
        from application.orchestration.support.clock import now_text
        assert re.fullmatch(r"[A-Z][a-z]+, \d{4}-\d{2}-\d{2}, \d{2}:\d{2} \(UTC[+-]\d{2}:\d{2}\)", now_text())

    def test_small_talk_and_refusals_do_not_pause_the_flow_by_prompt(self):
        from application.system_prompts.advanced import LoadSystemPrompt
        triage = LoadSystemPrompt(1)
        assert "greeting, thanks, small talk" in triage and "cannot do" in triage
        assert "ONE \"generation\" action" in LoadSystemPrompt(2)
