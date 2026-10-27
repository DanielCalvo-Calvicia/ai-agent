# pyright: reportOptionalMemberAccess=false, reportArgumentType=false
"""
Characterization ("golden") test of the message flow.

A scripted LLM returns canned JSON per phase and every call it receives is recorded
(phase, model, system prompt, user message, response format, sampling, tools). The
recorded sequence and the final reply are compared with tests/golden/flow_golden.json.

The golden file was first generated from the pre-refactor MessageFlowService and regenerated on purpose
when the four flows (identification, conversation, special, movement) replaced the two old ones. A refactor of
the orchestration must keep this test green without regenerating the file.
Regenerate on purpose with:  UPDATE_GOLDEN=1 python -m pytest tests/test_flow_golden.py
"""
import hashlib
import json
import os
import re
import sys
from typing import Any, Callable, Dict, List, Optional

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.inbound.dto.message import TextRequestDTO
from application.outbound.ports.llm_ports import LLMOutboundPort
from application.service.message_flow_service import MessageFlowService
from domain.entities.llm_request.payload import Payload
from domain.entities.llm_response.response import Response
from infrastructure.outbound.llm.response_mapper import build_response as _build_response

GOLDEN_PATH = os.path.join(PROJECT_ROOT, "tests", "golden", "flow_golden.json")
USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

MCP_LIST = [
    {
        "name": "aws_microservice",
        "type": "sse",
        "config": {"type": "sse", "url": "http://example.invalid/mcp/sse"},
    }
]

_ACTION_ID = re.compile(r"Action\(id=Id\(value='([^']+)'\)")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ===============================================
#  SCRIPTED LLM
# ===============================================

class ScriptedLLM(LLMOutboundPort):
    """
    Answers by response-format name. `overrides` maps a format name to a dict (or a
    callable returning a dict) that replaces the default canned answer.
    `post` maps a format name to a function that edits the built Response in place.
    """

    def __init__(
        self,
        overrides: Optional[Dict[str, Any]] = None,
        post: Optional[Dict[str, Callable[[Response], None]]] = None,
    ) -> None:
        self.overrides = overrides or {}
        self.post = post or {}
        self.calls: List[Dict[str, Any]] = []

    def is_available(self) -> bool:
        return True

    def ask(self, Payload: Payload) -> Response:
        rf = Payload.response_format
        name = rf.name if rf else "<text>"
        self.calls.append(self._record(Payload, name))

        if name == "<text>":
            return _build_response("Please tell me the missing details.", USAGE)

        data = self.overrides.get(name)
        if callable(data):
            data = data(Payload)
        if data is None:
            data = self._default(name, Payload)

        self.last_raw = data                                 # what "the LLM" answered, even if the mapper rejects it
        response = _build_response(data, USAGE)
        if name in self.post:
            self.post[name](response)
        return response

    @staticmethod
    def _record(payload: Payload, name: str) -> Dict[str, Any]:
        return {
            "format": name,
            "model": payload.model.id,
            "system_prompt_sha": _sha(payload.system_prompt.content) if payload.system_prompt else None,
            "system_prompt_len": len(payload.system_prompt.content) if payload.system_prompt else 0,
            "user_message": payload.message.content,
            "schema_sha": _sha(json.dumps(rf_schema(payload), sort_keys=True)),
            "temperature": payload.temperature.value if payload.temperature else None,
            "top_p": payload.top_p.value if payload.top_p else None,
            "max_tokens": payload.max_tokens.value if payload.max_tokens else None,
            "seed": payload.seed,
            "reasoning": repr(payload.reasoning),
            "intent": repr(payload.intent),
            "tools": json.dumps(payload.tools, sort_keys=True, default=repr),
        }

    @staticmethod
    def _default(name: str, payload: Payload) -> Dict[str, Any]:
        if name == "triage_specialist_phase1_response_format":
            return {
                "intent": {"primary": "information_request", "secondary": [], "confidence": 0.9},
                "user_goal": {"summary": "goal summary", "expected_outcome": "initial outcome"},
                "task_category": {"domain": "system", "type": "analysis", "complexity": "low"},
                "next_step": {"ready_to_execute": True, "status": "proceed",
                              "recommended_action": "plan", "blocking_reason": "",
                              "requested_user_input": []},
            }
        if name == "project_manager_phase2_response_format":
            return {
                "actions": [
                    {"id": "a1", "description": "think", "action_type": "analysis",
                     "dependencies": [], "required_inputs": [], "output": "", "error": "",
                     "mcp_context": {"server_id": "", "tool_name": "", "parameters": {}}},
                    {"id": "a2", "description": "call tool", "action_type": "mcp_tool_call",
                     "mcp_context": {"server_id": "aws_microservice", "tool_name": "get_weather",
                                     "parameters": {"city": "Madrid"}},
                     "dependencies": ["a1"], "required_inputs": [], "output": "", "error": ""},
                ],
                "next_step": {"ready_to_execute": True, "status": "proceed",
                              "recommended_action": "go", "blocking_reason": "",
                              "requested_user_input": []},
                "task_category_complexity": "low",
            }
        if name == "safety_quality_gatekeeper_phase3_response_format":
            return {
                "safety_and_validation": {"sensitive": False, "requires_confirmation": False},
                "next_step": {"ready_to_execute": True, "status": "proceed",
                              "recommended_action": "run", "blocking_reason": "",
                              "requested_user_input": []},
            }
        m = re.match(r"phase(\d)_single_action_response_format", name)
        if m:
            phase = m.group(1)
            found = _ACTION_ID.search(payload.message.content)
            action_id = found.group(1) if found else "unknown"
            return {"actions": [{"id": action_id, "description": "d", "action_type": "analysis",
                                 "dependencies": [], "required_inputs": [], "error": "",
                                 "mcp_context": {"server_id": "", "tool_name": "", "parameters": {}},
                                 "output": f"out-p{phase}-{action_id}"}]}
        if name == "motion_planner_phase20_response_format":
            return {
                "is_motion_request": True,
                "movements": [{"arm": "left", "degrees": 90, "direction": "forward"}],
                "spoken_reply": "Turning my left arm 90 degrees.",
                "next_step": {"ready_to_execute": True, "status": "complete",
                              "recommended_action": "", "blocking_reason": "",
                              "requested_user_input": []},
            }
        if name == "answer_checker_phase9_response_format":
            return {"verdict": "answered", "answer": "the answer of the user", "message_to_user": ""}
        if name == "draft_writer_phase7_response_format":
            return {"user_goal": {"summary": "s", "expected_outcome": "draft answer"}}
        if name == "editor_in_chief_phase8_response_format":
            return {
                "user_goal": {"summary": "s", "expected_outcome": "final answer"},
                "next_step": {"ready_to_execute": True, "status": "complete",
                              "recommended_action": "", "blocking_reason": "",
                              "requested_user_input": []},
            }
        raise AssertionError(f"unexpected response format: {name}")


def rf_schema(payload: Payload) -> Any:
    return payload.response_format.schema if payload.response_format else None


# ===============================================
#  SCENARIOS
# ===============================================

PM = "project_manager_phase2_response_format"
GATE = "safety_quality_gatekeeper_phase3_response_format"
TRIAGE = "triage_specialist_phase1_response_format"


def _action(id_, action_type="analysis", dependencies=(), subactions=(), required_inputs=()):
    """One planned action, shaped like the LLM answers it."""
    mcp = ({"server_id": "aws_microservice", "tool_name": "get_weather", "parameters": {"city": "Madrid"}}
           if action_type == "mcp_tool_call" else {"server_id": "", "tool_name": "", "parameters": {}})
    return {"id": id_, "description": f"step {id_}", "action_type": action_type,
            "dependencies": list(dependencies), "required_inputs": list(required_inputs),
            "mcp_context": mcp, "output": "", "error": "", "subactions": list(subactions)}


def _plan(*actions):
    return {"actions": list(actions), "task_category_complexity": "low",
            "next_step": {"ready_to_execute": True, "status": "proceed", "recommended_action": "",
                          "blocking_reason": "", "requested_user_input": []}}


def _triage_for(domain):
    """The triage answer that sends the message to the flow of this domain."""
    return {
        "intent": {"primary": "information_request", "secondary": [], "confidence": 0.9},
        "user_goal": {"summary": "goal summary", "expected_outcome": "initial outcome"},
        "task_category": {"domain": domain, "type": "generation", "complexity": "low"},
        "next_step": {"ready_to_execute": True, "status": "proceed", "recommended_action": "",
                      "blocking_reason": "", "requested_user_input": []},
    }


def _no_result(payload):
    """The MCP operator answers without an output (the tool failed)."""
    found = _ACTION_ID.search(payload.message.content)
    return {"actions": [{**_action(found.group(1), "mcp_tool_call"), "error": "tool unavailable"}]}


SCENARIOS: Dict[str, Dict[str, Any]] = {
    "full_path_with_mcp": {"message": "what is the weather", "llm": {}},
    "no_actions": {
        "message": "hello",
        "llm": {"overrides": {PM: {
            "actions": [],
            "next_step": {"ready_to_execute": True, "status": "proceed",
                          "recommended_action": "", "blocking_reason": "",
                          "requested_user_input": []},
            "task_category_complexity": "low"}}},
    },
    "pause_after_project_manager": {
        "message": "send it",
        "llm": {"overrides": {PM: {
            "actions": [_action("a1", required_inputs=["recipient"])],
            "next_step": {"ready_to_execute": False, "status": "awaiting_user_input",
                          "recommended_action": "", "blocking_reason": "missing recipient",
                          "requested_user_input": ["who is the recipient?"]},
            "task_category_complexity": "low"}}},
    },
    "pause_after_gatekeeper": {
        "message": "delete everything",
        "llm": {"overrides": {GATE: {
            "safety_and_validation": {"sensitive": True, "requires_confirmation": True},
            "next_step": {"ready_to_execute": False, "status": "awaiting_confirmation",
                          "recommended_action": "", "blocking_reason": "destructive",
                          "requested_user_input": []}}}},
    },
    "pause_without_details": {
        "message": "do the thing",
        "llm": {"overrides": {PM: {
            "actions": [],
            "next_step": {"ready_to_execute": False, "status": "awaiting_user_input",
                          "recommended_action": "", "blocking_reason": "",
                          "requested_user_input": []},
            "task_category_complexity": "low"}}},
    },
    "mcp_blocked_by_confirmation": {
        "message": "read my files",
        "llm": {"overrides": {GATE: {
            "safety_and_validation": {"sensitive": True, "requires_confirmation": True},
            "next_step": {"ready_to_execute": True, "status": "proceed",
                          "recommended_action": "", "blocking_reason": "",
                          "requested_user_input": []}}}},
    },
    "action_with_subactions": {
        "message": "plan my day",
        "llm": {"overrides": {PM: _plan(
            _action("1", subactions=[_action("1.1"), _action("1.2", dependencies=["1.1"])]),
            _action("2", dependencies=["1"]))}},
    },
    "mcp_result_feeds_a_cognitive_action": {
        "message": "tell me if I need an umbrella",
        "llm": {"overrides": {PM: _plan(
            _action("2", dependencies=["1"]),
            _action("1", "mcp_tool_call"))}},
    },
    "mcp_tool_fails_then_dependents_are_skipped": {
        "message": "tell me if I need an umbrella",
        "llm": {"overrides": {
            PM: _plan(_action("1", "mcp_tool_call"), _action("2", dependencies=["1"]), _action("3")),
            "phase5_single_action_response_format": _no_result}},
    },
    "unknown_and_circular_dependencies": {
        "message": "do it",
        "llm": {"overrides": {PM: _plan(
            _action("1", dependencies=["9"]),
            _action("2", dependencies=["3"]),
            _action("3", dependencies=["2"]),
            _action("4"))}},
    },
    "communication_goes_to_the_conversation_flow": {
        "message": "hello there",
        "llm": {"overrides": {TRIAGE: _triage_for("communication")}},
    },
    "movement_goes_to_the_movement_flow_and_is_announced": {
        "message": "raise your left arm a quarter turn",
        "llm": {"overrides": {TRIAGE: _triage_for("movement")}},
    },
    "movement_that_brain_does_not_want_spoken": {
        "message": "raise your left arm a quarter turn",
        "speak_movements": False,
        "llm": {"overrides": {TRIAGE: _triage_for("movement")}},
    },
    "pause_after_triage": {
        "message": "do the thing",
        "llm": {"overrides": {TRIAGE: {
            "intent": {"primary": "clarification_request", "secondary": [], "confidence": 0.5},
            "user_goal": {"summary": "unclear", "expected_outcome": "unclear"},
            "task_category": {"domain": "system", "type": "analysis", "complexity": "low"},
            "next_step": {"ready_to_execute": False, "status": "awaiting_user_input",
                          "recommended_action": "ask_user_for_missing_information",
                          "blocking_reason": "the request is not clear",
                          "requested_user_input": ["What do you want me to do?"]}}}},
    },
}


def _run(scenario: Dict[str, Any]) -> Dict[str, Any]:
    llm = ScriptedLLM(**scenario["llm"])
    service = MessageFlowService(outbound_port=llm, mcp_list=MCP_LIST)
    reply = service.text(TextRequestDTO(user_id="tester", session_id="s1", content=scenario["message"],
                                        speak_movements=scenario.get("speak_movements", True))).content
    metrics = service.metrics.summary()
    for record in metrics["request_log"]:
        record.pop("request_id")
    return {"reply": reply, "calls": llm.calls, "metrics": metrics}


FIXED_NOW = "Monday, 2026-01-05, 09:00 (UTC+00:00)"


@pytest.fixture(autouse=True)
def _project_cwd(monkeypatch):
    # Prompts, schemas and MCP configs are resolved relative to the working directory.
    monkeypatch.chdir(PROJECT_ROOT)
    # The system prompt carries the current date and time. Fix it so the recorded calls do not change.
    monkeypatch.setattr("application.system_prompts.general.now_text", lambda: FIXED_NOW)


def _load_golden() -> Dict[str, Any]:
    if not os.path.exists(GOLDEN_PATH):
        return {}
    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_flow_matches_golden(name: str):
    actual = _run(SCENARIOS[name])
    actual = json.loads(json.dumps(actual))  # normalise to plain JSON types

    if os.environ.get("UPDATE_GOLDEN") == "1":
        golden = _load_golden()
        golden[name] = actual
        os.makedirs(os.path.dirname(GOLDEN_PATH), exist_ok=True)
        with open(GOLDEN_PATH, "w", encoding="utf-8") as f:
            json.dump(golden, f, indent=2, sort_keys=True, ensure_ascii=False)
        return

    golden = _load_golden()
    assert name in golden, f"no golden data for {name}; run with UPDATE_GOLDEN=1 on the reference code"
    assert actual["reply"] == golden[name]["reply"]
    assert [c["format"] for c in actual["calls"]] == [c["format"] for c in golden[name]["calls"]]
    assert actual["calls"] == golden[name]["calls"]
    assert actual["metrics"] == golden[name]["metrics"]
