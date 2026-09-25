"""
The fast path: a triage answer classified as pure information/conversation (not a task to
plan) skips project manager, the safety gate and action execution. Phases 2-6 are pure
overhead when there is nothing to plan, validate or execute. This module also guards the
regression that motivated the extra intent check: a "generation"/"low" classification alone
is NOT enough — the project manager's own prompt uses "generation" for real multi-step
writing tasks too (e.g. "make a table of my family"), which still needs a plan.
"""
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.orchestration import fast_path
from application.orchestration.flow_state import FlowState
from application.orchestration.robot_directive import RobotDirective
from application.service.message_flow_service import MessageFlowService
from domain.value_objects.intent.intent import create_intent
from domain.value_objects.task_category.task_category import create_task_category
from test_flow_golden import PM, TRIAGE, ScriptedLLM, _action, _plan


@pytest.fixture(autouse=True)
def _project_cwd(monkeypatch):
    monkeypatch.chdir(PROJECT_ROOT)
    monkeypatch.setattr("application.system_prompts.advanced.now_text", lambda: "Monday, 2026-01-05, 09:00 (UTC+00:00)")


def _state(intent_primary="information_request", task_type="generation", complexity="low", needs_input=False):
    state = FlowState(message="hi")
    state.intent = create_intent(primary=intent_primary, secondary=[], confidence=0.9)
    state.task_category = create_task_category(domain_value="system", type_value=task_type, complexity_value=complexity)
    if needs_input:
        from domain.value_objects.next_step.next_step import create_next_step
        state.next_step = create_next_step(
            ready_to_execute_value=False, status_value="awaiting_user_input", recommended_action_value="",
            blocking_reason_value="", requested_user_input_value=["what?"])
    return state


# ===============================================
#  applies(): unit tests
# ===============================================

class TestFastPathApplies:
    def test_fires_for_a_plain_information_request(self):
        assert fast_path.applies(_state()) is True

    def test_fires_for_a_clarification_request(self):
        assert fast_path.applies(_state(intent_primary="clarification_request")) is True

    def test_does_not_fire_for_a_task_execution_even_when_generation_and_low(self):
        # The regression this heuristic must never repeat: "make a table of my family" is
        # intent=task_execution, type=generation, complexity=low, and needs a real plan.
        assert fast_path.applies(_state(intent_primary="task_execution")) is False

    def test_does_not_fire_when_complexity_is_not_low(self):
        assert fast_path.applies(_state(complexity="medium")) is False

    def test_does_not_fire_when_type_is_not_generation(self):
        assert fast_path.applies(_state(task_type="analysis")) is False

    def test_does_not_fire_when_the_flow_needs_user_input(self):
        assert fast_path.applies(_state(needs_input=True)) is False

    def test_does_not_fire_before_triage_has_run(self):
        assert fast_path.applies(FlowState(message="hi")) is False

    def test_disabled_by_the_env_var(self, monkeypatch):
        monkeypatch.setenv(fast_path.ENABLED_VARIABLE, "0")
        assert fast_path.applies(_state()) is False

    def test_enabled_by_default(self, monkeypatch):
        monkeypatch.delenv(fast_path.ENABLED_VARIABLE, raising=False)
        assert fast_path.applies(_state()) is True


# ===============================================
#  Full pipeline: the fast path actually skips calls
# ===============================================

_CHITCHAT_TRIAGE = {
    "intent": {"primary": "information_request", "secondary": [], "confidence": 0.95},
    "user_goal": {"summary": "greeting", "expected_outcome": "a friendly reply"},
    "task_category": {"domain": "system", "type": "generation", "complexity": "low"},
    "next_step": {"ready_to_execute": True, "status": "proceed",
                  "recommended_action": "", "blocking_reason": "", "requested_user_input": []},
}

# Same generation/low classification, but a real task (the project_manager must still run).
_TASK_TRIAGE = {
    "intent": {"primary": "task_execution", "secondary": [], "confidence": 0.9},
    "user_goal": {"summary": "a table of the family", "expected_outcome": "a table"},
    "task_category": {"domain": "writing", "type": "generation", "complexity": "low"},
    "next_step": {"ready_to_execute": True, "status": "proceed",
                  "recommended_action": "", "blocking_reason": "", "requested_user_input": []},
}


def _formats(llm) -> list:
    return [c["format"] for c in llm.calls]


class TestPipelineFastPath:
    def test_chitchat_skips_planning_the_gate_and_action_execution(self):
        llm = ScriptedLLM(overrides={TRIAGE: _CHITCHAT_TRIAGE})
        service = MessageFlowService(outbound_port=llm, mcp_list=[])

        result = service.main_flow("hello there")

        assert _formats(llm) == [
            "triage_specialist_phase1_response_format",
            "draft_writer_phase7_response_format",
            "editor_in_chief_phase8_response_format",
        ]
        assert result.reply == "final answer"
        assert result.directive is None

    def test_a_real_task_classified_generation_low_still_gets_a_plan(self):
        # Same task_category as the chit-chat case; only intent differs. Must NOT fast-path.
        llm = ScriptedLLM(overrides={
            TRIAGE: _TASK_TRIAGE,
            PM: _plan(_action("1", "generation")),
        })
        service = MessageFlowService(outbound_port=llm, mcp_list=[])

        result = service.main_flow("make a table of my family")

        assert "project_manager_phase2_response_format" in _formats(llm)
        assert "safety_quality_gatekeeper_phase3_response_format" in _formats(llm)
        assert result.reply == "final answer"

    def test_a_movement_request_is_never_fast_pathed(self):
        # task_execution + generation/low, like the table example: must go through the project
        # manager (the only phase that can plan a robot_action) and still produce a directive.
        movement_triage = {
            "intent": {"primary": "task_execution", "secondary": [], "confidence": 0.9},
            "user_goal": {"summary": "move the left arm", "expected_outcome": "the arm moves"},
            "task_category": {"domain": "operations", "type": "generation", "complexity": "low"},
            "next_step": {"ready_to_execute": True, "status": "proceed",
                          "recommended_action": "", "blocking_reason": "", "requested_user_input": []},
        }

        def _worker_output(_payload):
            return {"actions": [{"id": "1", "description": "d", "action_type": "robot_action",
                                 "dependencies": [], "required_inputs": [], "error": "",
                                 "mcp_context": {"server_id": "", "tool_name": "", "parameters": {}},
                                 "output": "arm=left degrees=90 direction=forward"}]}

        llm = ScriptedLLM(overrides={
            TRIAGE: movement_triage,
            PM: _plan(_action("1", "robot_action")),
            "phase4_single_action_response_format": _worker_output,
        })
        service = MessageFlowService(outbound_port=llm, mcp_list=[])

        result = service.main_flow("move your left arm 90 degrees")

        assert "project_manager_phase2_response_format" in _formats(llm)
        assert "safety_quality_gatekeeper_phase3_response_format" in _formats(llm)
        assert result.directive == RobotDirective(arm="left", degrees=90.0, direction="forward")

    def test_disabling_the_fast_path_forces_the_full_pipeline(self, monkeypatch):
        monkeypatch.setenv(fast_path.ENABLED_VARIABLE, "0")
        llm = ScriptedLLM(overrides={TRIAGE: _CHITCHAT_TRIAGE})
        service = MessageFlowService(outbound_port=llm, mcp_list=[])

        service.main_flow("hello there")

        assert "project_manager_phase2_response_format" in _formats(llm)
        assert "safety_quality_gatekeeper_phase3_response_format" in _formats(llm)
