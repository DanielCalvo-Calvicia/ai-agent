# pyright: reportOptionalMemberAccess=false, reportArgumentType=false
"""
Characterization ("golden") test of the message flow.

A scripted LLM returns canned JSON per phase and every call it receives is recorded
(phase, model, system prompt, user message, response format, sampling, tools). The
recorded sequence and the final reply are compared with tests/golden/flow_golden.json.

The golden file was first generated from the pre-refactor MessageFlowService and regenerated on purpose
when the four flows (identification, conversation, special, movement) replaced the two old ones. A refactor of
the orchestration must keep this test green without regenerating the file.

T-05.10 added one block per PROFILE (`profile_identification`, `profile_chat`, `profile_special`, `profile_movement`,
`profile_gesture`): the same recording for the profile alone, run the way the service runs it (the real profile, its models,
its inputs). The other scenarios are the client's chain (tests/brain_chain.py); a test checks that the request of every step
in a profile block is the request that step had in the chain, only the model being the profile's (`default` and `dynamics`
have no block: they run the steps of `special`, tested in tests/test_profiles_mock.py).
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
from brain_chain import ChainedMessageFlowService as MessageFlowService
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


def _without_the_run_keys(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    The golden file pins the tokens of every call as they were. The keys T-05.15 added to the records (profile, flow, step, client,
    profile_hash, cost_usd) and `total_cost_usd` have their own tests (test_metrics_and_hash.py); leaving them out here keeps the
    file byte-identical, which is the proof that no request changed.
    """
    metrics.pop("total_cost_usd", None)
    for record in metrics["request_log"]:
        record.pop("request_id")
        for key in ("profile", "flow", "step", "client", "profile_hash", "cost_usd"):
            record.pop(key, None)
    return metrics


def _run(scenario: Dict[str, Any]) -> Dict[str, Any]:
    llm = ScriptedLLM(**scenario["llm"])
    service = MessageFlowService(outbound_port=llm, mcp_list=MCP_LIST)
    reply = service.text(TextRequestDTO(user_id="tester", session_id="s1", content=scenario["message"],
                                        speak_movements=scenario.get("speak_movements", True))).content
    metrics = _without_the_run_keys(service.metrics.summary())
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


# ===============================================
#  ONE BLOCK PER PROFILE (T-05.10)
# ===============================================

from application.assembly.assemble import assemble
from application.assembly.config_snapshot import build_snapshot
from application.runtime.profile.inputs import read_inputs
from application.runtime.state.response_json import response_to_json
from application.service.message_flow_service import MessageFlowService as OneProfileService
from infrastructure.outbound.config.file_source import FileConfigSource
from infrastructure.outbound.llm.response_mapper import read_response_json

REPLY_TO_GIVE_A_GESTURE = "Hello! How can I help you today?"


def _agent():
    """The real profiles of profiles/, with the models each one names (the golden pins them)."""
    agent = assemble(build_snapshot(FileConfigSource(PROJECT_ROOT)))
    agent.raise_on_errors()
    return agent


def _identification_output(overrides: Dict[str, Any]) -> Dict[str, Any]:
    """What a client sends as `inputs`: the Response the `identification` profile returned for the message."""
    service = OneProfileService(outbound_port=ScriptedLLM(overrides=overrides), mcp_list=[], agent=_agent(), profile="identification")
    service.text(TextRequestDTO(user_id="tester", session_id="s1", content="hello there"))
    return response_to_json(service.last_response)


def _profile_scenarios() -> Dict[str, Dict[str, Any]]:
    from test_expression import feeling

    communication = SCENARIOS["communication_goes_to_the_conversation_flow"]
    return {
        "profile_identification": {"profile": "identification", **communication},
        "profile_chat": {"profile": "chat", "message": "hello there", "llm": {},
                         "inputs": lambda: _identification_output(communication["llm"]["overrides"])},
        "profile_special": {"profile": "special", **SCENARIOS["no_actions"]},
        "profile_movement": {"profile": "movement", **SCENARIOS["movement_goes_to_the_movement_flow_and_is_announced"]},
        "profile_gesture": {"profile": "gesture", "message": "hello there", "llm": {"overrides": feeling()},
                            "inputs": lambda: {"reply": REPLY_TO_GIVE_A_GESTURE}},
    }


PROFILE_SCENARIOS = ["profile_identification", "profile_chat", "profile_special", "profile_movement", "profile_gesture"]


def _run_profile(scenario: Dict[str, Any]) -> Dict[str, Any]:
    agent = _agent()
    profile = agent.profile(scenario["profile"])
    inputs = scenario["inputs"]() if "inputs" in scenario else None
    values = read_inputs(profile, inputs, read_response_json) if inputs is not None else {}
    llm = ScriptedLLM(**scenario["llm"])
    service = OneProfileService(outbound_port=llm, mcp_list=MCP_LIST, agent=agent, profile=scenario["profile"], inputs=values)
    reply = service.text(TextRequestDTO(user_id="tester", session_id="s1", content=scenario["message"],
                                        speak_movements=scenario.get("speak_movements", True))).content
    metrics = _without_the_run_keys(service.metrics.summary())
    return {"reply": reply, "calls": llm.calls, "metrics": metrics}


@pytest.mark.parametrize("name", PROFILE_SCENARIOS)
def test_profile_matches_golden(name: str):
    actual = json.loads(json.dumps(_run_profile(_profile_scenarios()[name])))

    if os.environ.get("UPDATE_GOLDEN") == "1":
        golden = _load_golden()
        golden[name] = actual
        with open(GOLDEN_PATH, "w", encoding="utf-8") as f:
            json.dump(golden, f, indent=2, sort_keys=True, ensure_ascii=False)
        return

    golden = _load_golden()
    assert name in golden, f"no golden data for {name}; run with UPDATE_GOLDEN=1"
    assert actual["reply"] == golden[name]["reply"]
    assert [c["format"] for c in actual["calls"]] == [c["format"] for c in golden[name]["calls"]]
    assert actual["calls"] == golden[name]["calls"]
    assert actual["metrics"] == golden[name]["metrics"]


# The request of a step must be the request it had before profiles: the same system prompt, user message, schema, sampling and tools.
# Only the model differs (it is the profile's: pinned by the block itself).
def _same_request_whatever_the_model(call: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in call.items() if key != "model"}


# profile block -> (the scenario of the client's chain that has the same requests, the calls of it that belong to the profile)
CHAIN_OF_PROFILE = {
    "profile_identification": ("communication_goes_to_the_conversation_flow", slice(0, 1)),      # the triage
    "profile_chat": ("communication_goes_to_the_conversation_flow", slice(1, None)),             # then the writer and the editor
    "profile_special": ("no_actions", slice(0, None)),                                           # the triage, then the special steps
    "profile_movement": ("movement_goes_to_the_movement_flow_and_is_announced", slice(1, None)),   # the planner
}


@pytest.mark.parametrize("block", list(CHAIN_OF_PROFILE))
def test_the_requests_of_a_profile_are_the_requests_of_each_step_before_profiles(block: str):
    golden = _load_golden()
    chain_name, part = CHAIN_OF_PROFILE[block]
    before = [_same_request_whatever_the_model(c) for c in golden[chain_name]["calls"][part]]
    now = [_same_request_whatever_the_model(c) for c in golden[block]["calls"]]
    assert now == before
    assert before                                                        # and it is not an empty comparison


def test_the_block_of_special_is_the_triage_followed_by_the_special_requests():
    calls = _load_golden()["profile_special"]["calls"]
    assert [c["format"].split("_response")[0] for c in calls][:2] == ["triage_specialist_phase1", "project_manager_phase2"]
    assert calls[-1]["format"].startswith("editor_in_chief")


def test_each_profile_block_pins_the_models_of_its_profile():
    golden = _load_golden()
    assert {c["model"] for c in golden["profile_identification"]["calls"]} == {"gemini-3.1-flash-lite"}                 # proven
    assert {c["model"] for c in golden["profile_chat"]["calls"]} == {"claude-haiku-4-5"}                                # claude_haiku
    by_step = {c["format"].split("_response")[0]: c["model"] for c in golden["profile_special"]["calls"]}              # claude_mixed
    assert by_step["triage_specialist_phase1"] == "claude-haiku-4-5" and by_step["project_manager_phase2"] == "claude-sonnet-5-5"
    assert by_step["draft_writer_phase7"] == "claude-sonnet-5-5" and by_step["editor_in_chief_phase8"] == "claude-sonnet-5-5"
    assert {c["model"] for c in golden["profile_movement"]["calls"]} == {"gemini-3.1-flash-lite"}                       # proven
    assert {c["model"] for c in golden["profile_gesture"]["calls"]} == {"gemini-3.1-flash-lite"}                        # proven
