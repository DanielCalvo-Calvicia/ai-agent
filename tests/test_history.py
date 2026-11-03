# T-05.8: a session keeps one entry per request (the user's words, the reply and the structured Response of the run), and the steps read
# them exactly as they read the text pairs the session kept before (PR-005 section 7, Q09-4).
import dataclasses
import os

import pytest

from application.engine.assemble import assemble
from application.engine.config_snapshot import build_snapshot
from application.engine.state.flow_state import FlowState
from application.engine.state.history import HistoryEntry, messages_of, response_of
from application.engine.state.paused_run import FlowResult
from application.flows.registry import FLOWS
from application.inbound.dto.session import MessageReceivedRequestDTO, StartSessionRequestDTO
from application.service.message_flow_service import MessageFlowService
from application.service.session_service import SessionService
from application.service.user_session import UserSession
from application.inbound.dto.message import TextRequestDTO
from domain.value_objects.llm_request.message import Message, Role
from infrastructure.outbound.config.file_source import FileConfigSource

from brain_chain import ChainedSessionService
from test_expression import feeling
from test_flow_golden import SCENARIOS, ScriptedLLM
from test_resume import CHECK, Script, _verdict
from test_flow_golden import TRIAGE as TRIAGE_FORMAT
from test_resume import TRIAGE_ASKS, TRIAGE_OK

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def old_remember(history, user_text, reply, max_turns):
    """What UserSession.remember did when the session kept text pairs (kept here as the reference)."""
    history.append(Message(Role.USER, user_text))
    if reply.strip():
        history.append(Message(Role.ASSISTANT, reply))
    keep = 2 * max(max_turns, 0)
    if len(history) > keep:
        del history[:len(history) - keep]


def pairs(history):
    return [(m.role, m.content) for m in history]


@pytest.fixture(scope="module")
def agent():
    built = assemble(build_snapshot(FileConfigSource(PROJECT_ROOT)), known_flows={flow.name for flow in FLOWS})
    built.raise_on_errors()
    return built


def message(service, session_id, text):
    return service.message_received(MessageReceivedRequestDTO(user_id="tester", session_id=session_id, message=text))


def started(service):
    return service.start_session(StartSessionRequestDTO(user_id="tester", username="t")).session_id


# ===============================================
#  THE ENTRY AND THE MESSAGES THE STEPS READ
# ===============================================

class TestTheMessagesAreTheSameAsBefore:
    @pytest.mark.parametrize("turns", [1, 2, 3, 6])
    def test_every_exchange_with_a_reply_reads_as_the_text_pairs_did(self, turns):
        session, old = UserSession(session_id="s", username="u"), []
        for i in range(9):
            session.remember(f"question {i}", f"answer {i}", turns)
            old_remember(old, f"question {i}", f"answer {i}", turns)
            assert pairs(session.history) == pairs(old)

    def test_an_exchange_with_no_reply_is_only_the_users_message(self):
        session = UserSession(session_id="s", username="u")
        session.remember("hello", "  ", 3)
        assert pairs(session.history) == [(Role.USER, "hello")]

    def test_the_session_keeps_the_last_n_requests_not_the_last_2n_messages(self):
        session = UserSession(session_id="s", username="u")
        for i in range(4):
            session.remember(f"q{i}", "" if i % 2 else f"a{i}", 2)       # a request with no reply is still one request
        assert [e.message for e in session.entries] == ["q2", "q3"]

    def test_zero_turns_keeps_nothing(self):
        session = UserSession(session_id="s", username="u")
        session.remember("hi", "hello", 0)
        assert session.entries == [] and session.history == []

    def test_the_history_is_a_new_list_each_time_so_a_step_cannot_change_the_session(self):
        session = UserSession(session_id="s", username="u")
        session.remember("hi", "hello", 3)
        session.history.append(Message(Role.USER, "injected"))
        assert len(session.history) == 2

    def test_messages_of_an_empty_list_is_empty(self):
        assert messages_of([]) == []

    def test_an_entry_cannot_be_changed(self):
        entry = HistoryEntry("hi", "hello")
        with pytest.raises(dataclasses.FrozenInstanceError):
            entry.reply = "other"


class TestTheResponseOfARun:
    def classified(self):
        llm = ScriptedLLM()
        from application.engine.support.metrics import SessionMetrics
        from application.engine.pipeline import Pipeline
        from application.flows.identification import IDENTIFICATION_FLOW
        return Pipeline(llm, [], SessionMetrics(), flow=IDENTIFICATION_FLOW).run("hello")

    def test_a_run_with_a_user_goal_gives_a_response_with_every_field_of_the_state(self):
        result = self.classified()
        response = response_of(result)
        assert response is not None
        assert response.user_goal is result.state.user_goal and response.task_category is result.state.task_category
        assert response.intent is result.state.intent and response.next_step is result.state.next_step

    def test_as_response_is_the_other_side_of_load_from(self):
        state = self.classified().state
        other = FlowState(message="x")
        other.load_from(state.as_response())
        for name in ("intent", "user_goal", "mcp_routing", "task_category", "actions", "missing_information", "constraints",
                     "safety_and_validation", "next_step"):
            assert getattr(other, name) is getattr(state, name), name

    def test_a_run_with_no_user_goal_has_no_response(self):
        assert response_of(FlowResult(reply="", state=FlowState(message="hello"))) is None

    def test_a_result_with_no_state_has_no_response(self):
        assert response_of(FlowResult(reply="x")) is None


# ===============================================
#  THE SERVICE REMEMBERS ENTRIES
# ===============================================

class TestTheServiceKeepsEntries:
    def test_each_request_adds_an_entry_with_its_words_its_reply_and_its_response(self):
        scenario = SCENARIOS["communication_goes_to_the_conversation_flow"]
        service = ChainedSessionService(outbound_port=ScriptedLLM(**scenario["llm"]), mcp_list=[])
        sid = started(service)
        first = message(service, sid, scenario["message"])
        entries = service.sessions[sid].entries
        assert len(entries) == 1 and entries[0].message == scenario["message"] and entries[0].reply == first.response
        assert entries[0].response is not None and entries[0].response.user_goal is not None
        assert entries[0].response.user_goal.expected_outcome.get_value()

    def test_the_second_request_reads_the_first_as_it_did_before(self):
        scenario = SCENARIOS["communication_goes_to_the_conversation_flow"]
        llm = ScriptedLLM(**scenario["llm"])
        service = ChainedSessionService(outbound_port=llm, mcp_list=[])
        sid = started(service)
        first = message(service, sid, scenario["message"])
        message(service, sid, "and now?")
        triage_inputs = [c for c in llm.calls if c["format"] == TRIAGE_FORMAT]
        assert f"user: {scenario['message']}" in str(triage_inputs[1]) and f"assistant: {first.response}" in str(triage_inputs[1])

    def test_the_history_keeps_the_last_n_requests(self):
        scenario = SCENARIOS["communication_goes_to_the_conversation_flow"]
        service = ChainedSessionService(outbound_port=ScriptedLLM(**scenario["llm"]), mcp_list=[], history_turns=2)
        sid = started(service)
        for text in ("one", "two", "three"):
            message(service, sid, text)
        assert [e.message for e in service.sessions[sid].entries] == ["two", "three"]

    def test_a_question_to_the_user_is_remembered_as_the_reply_with_the_response_of_the_run(self):
        llm = ScriptedLLM(overrides={TRIAGE_FORMAT: Script(TRIAGE_ASKS, TRIAGE_OK), CHECK: Script(_verdict("answered", "Ana"))})
        service = ChainedSessionService(outbound_port=llm, mcp_list=[])
        sid = started(service)
        asked = message(service, sid, "Make a table")
        assert asked.awaiting_user_input and service.sessions[sid].entries[0].reply == asked.response
        assert service.sessions[sid].entries[0].response is not None

    def test_a_failed_message_adds_nothing(self):
        class Failing(ScriptedLLM):
            def ask(self, payload):
                raise ValueError("boom")
        service = ChainedSessionService(outbound_port=Failing(), mcp_list=[])
        sid = started(service)
        assert message(service, sid, "hi").success is False
        assert service.sessions[sid].entries == []


class TestProductionProfiles:
    def test_the_default_profile_adds_an_entry_with_a_response(self, agent):
        scenario = SCENARIOS["no_actions"]
        service = SessionService(outbound_port=ScriptedLLM(**scenario["llm"]), mcp_list=[], agent=agent)
        sid = started(service)
        message(service, sid, scenario["message"])
        entry = service.sessions[sid].entries[0]
        assert entry.message == scenario["message"] and entry.response is not None and entry.response.task_category is not None

    def test_the_identification_profile_adds_an_entry_with_no_reply(self, agent):
        service = SessionService(outbound_port=ScriptedLLM(), mcp_list=[], agent=agent, profile="identification")
        sid = started(service)
        message(service, sid, "hello")
        entry = service.sessions[sid].entries[0]
        assert entry.reply == "" and entry.response is not None and entry.response.task_category is not None
        assert pairs(service.sessions[sid].history) == [(Role.USER, "hello")]

    def test_the_gesture_profile_has_no_user_goal_so_it_adds_no_entry(self, agent):
        service = MessageFlowService(outbound_port=ScriptedLLM(overrides=feeling()), mcp_list=[], agent=agent, profile="gesture")
        service.text(TextRequestDTO(user_id="tester", session_id="s", content="hello"))
        assert service.last_response is None

    def test_the_session_of_a_gesture_profile_stays_empty(self, agent):
        service = SessionService(outbound_port=ScriptedLLM(overrides=feeling()), mcp_list=[], agent=agent, profile="gesture")
        sid = started(service)
        answer = service.message_received(MessageReceivedRequestDTO(user_id="tester", session_id=sid, message="hello",
                                                                    inputs={"reply": "Hello there!"}))
        assert answer.success
        assert service.sessions[sid].entries == [] and service.sessions[sid].history == []


class TestTheUsersWordsAreNotLogged:
    def test_a_message_and_its_reply_do_not_reach_the_log(self, capsys):
        scenario = SCENARIOS["communication_goes_to_the_conversation_flow"]
        service = ChainedSessionService(outbound_port=ScriptedLLM(**scenario["llm"]), mcp_list=[])
        sid = started(service)
        reply = message(service, sid, "zzqq remembered words 4711").response
        out = capsys.readouterr()
        assert "zzqq remembered words 4711" not in out.out + out.err
        assert reply and reply not in out.out + out.err
