# pyright: reportOptionalMemberAccess=false, reportArgumentType=false
"""T-08.10 (ADR-019): a profile can list its own `steps` and run them, with no flow file.

Until then `assemble()` accepted a profile's `steps` and the runner refused them. A profile with the same steps as a flow file must run
exactly like it: the same calls, the same pause and resume, the same result.
"""
import copy
import os

import pytest

from application.assembly.assemble import assemble
from application.assembly.config_snapshot import build_snapshot
from application.dtos.inbound.message import TextRequestDTO
from application.runtime.profile.runner import ProfileMismatch, ProfileRunner
from application.runtime.step.metrics import SessionMetrics
from infrastructure.outbound.config.file_source import FileConfigSource
from infrastructure.outbound.llm.shared.schemas.anthropic_schema import anthropic_schema_problems
from infrastructure.outbound.mcp.config.loader import load_tool_snapshot
from test_flow_golden import SCENARIOS, ScriptedLLM, _identification_output, OneProfileService, read_inputs, read_response_json
from test_resume import CHECK, Script, _verdict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TOKEN = "b" * 64
MCP_LIST = [{"name": "dynamics_microservice", "type": "streamable_http", "config": {"url": "http://x"}}]


def own_profile(from_profile, steps, snapshot, **extra):
    """The profile `from_profile` with its `flow` replaced by `steps` (and what a flow file says about them)."""
    data = copy.deepcopy(snapshot.profiles[from_profile])
    data.pop("flow", None)
    data.pop("tested", None)
    return {**data, "name": "own_" + from_profile, "token_sha256": TOKEN, "steps": steps, **extra}


def assembled(*profiles):
    """The real agent plus the profiles given as (name, data); a problem stops the test."""
    snapshot = build_snapshot(FileConfigSource(PROJECT_ROOT))
    for name, make in profiles:
        snapshot.profiles[name] = make(snapshot)
    return assemble(snapshot, mcp_servers=load_tool_snapshot(), schema_rules={"anthropic": anthropic_schema_problems}), snapshot


CHAT_STEPS = ["draft_writer", {"step": "editor_in_chief", "retry_on_status": True}]
SPECIAL_STEPS = [
    {"step": "triage_specialist", "pause_if": "needs_user_input", "retry_on_status": True},
    {"step": "project_manager", "pause_if": "needs_user_input", "retry_on_status": True},
    {"step": "safety_quality_gatekeeper", "pause_if": "needs_user_input", "retry_on_status": True},
    "action_executor", "draft_writer", {"step": "editor_in_chief", "retry_on_status": True},
]


@pytest.fixture(scope="module")
def agent():
    built, _ = assembled(
        ("own_chat", lambda s: own_profile("chat", CHAT_STEPS, s)),
        ("own_special", lambda s: own_profile("special", SPECIAL_STEPS, s, on_pause="user_clarification", on_resume="answer_checker",
                                               result_from="editor_in_chief")),
    )
    built.raise_on_errors()
    return built


def run_chat(agent, profile):
    scenario = {"message": "hello there", "llm": {}}
    llm = ScriptedLLM(**scenario["llm"])
    inputs = _identification_output(SCENARIOS["communication_goes_to_the_conversation_flow"]["llm"]["overrides"])
    values = read_inputs(agent.profile(profile), inputs, read_response_json)
    service = OneProfileService(outbound_port=llm, mcp_list=MCP_LIST, agent=agent, profile=profile, inputs=values)
    reply = service.text(TextRequestDTO(user_id="tester", session_id="s1", content=scenario["message"])).content
    return reply, llm.calls, service


def runner(llm, agent):
    return ProfileRunner(llm, MCP_LIST, SessionMetrics(), None, agent)


# ---------------------------------------------------------------- assembling

def test_a_profile_with_its_own_steps_assembles_and_its_flow_is_built_and_named_like_the_profile(agent):
    profile = agent.profile("own_chat")

    assert agent.problems == {} and profile.flow_name is None
    assert profile.steps == ["draft_writer", "editor_in_chief"]
    assert profile.flow is not None and profile.flow.name == "own_chat"


def test_a_profile_that_names_a_flow_has_no_own_flow(agent):
    assert agent.profile("chat").flow is None and agent.profile("chat").flow_name == "conversation"


def test_the_hash_covers_the_steps_so_a_change_of_the_steps_changes_it():
    first, _ = assembled(("own_chat", lambda s: own_profile("chat", CHAT_STEPS, s)))
    other, _ = assembled(("own_chat", lambda s: own_profile("chat", ["draft_writer", "editor_in_chief"], s)))

    assert first.profile("own_chat").profile_hash != other.profile("own_chat").profile_hash


# ---------------------------------------------------------------- the same behaviour as a flow file

def test_the_same_steps_as_a_flow_file_give_the_same_calls_and_the_same_reply(agent):
    reply_file, calls_file, _ = run_chat(agent, "chat")
    reply_own, calls_own, service = run_chat(agent, "own_chat")

    assert reply_own == reply_file
    assert [c["format"] for c in calls_own] == [c["format"] for c in calls_file]
    assert [c["user_message"] for c in calls_own] == [c["user_message"] for c in calls_file]
    assert [c["system_prompt_sha"] for c in calls_own] == [c["system_prompt_sha"] for c in calls_file]


def test_the_flow_of_the_answer_and_of_the_metrics_is_the_name_of_the_profile(agent):
    _, _, service = run_chat(agent, "own_chat")

    assert service.metrics.flow == "own_chat"


def test_a_run_that_asked_the_user_a_question_is_resumed_by_the_same_profile(agent):
    scenario = SCENARIOS["pause_after_project_manager"]

    paused = runner(ScriptedLLM(**scenario["llm"]), agent).run("own_special", scenario["message"])
    assert paused.paused is not None and paused.flow == "own_special"

    resumed = runner(ScriptedLLM(overrides={CHECK: Script(_verdict("answered", "Ana"))}), agent).run("own_special", "to Ana", paused=paused.paused)
    assert resumed.flow == "own_special" and resumed.paused is None and resumed.reply


def test_the_same_steps_pause_at_the_same_place_as_the_flow_file(agent):
    scenario = SCENARIOS["pause_after_project_manager"]
    file_llm, own_llm = ScriptedLLM(**scenario["llm"]), ScriptedLLM(**scenario["llm"])

    runner(file_llm, agent).run("special", scenario["message"])
    runner(own_llm, agent).run("own_special", scenario["message"])

    assert [c["format"] for c in own_llm.calls] == [c["format"] for c in file_llm.calls]


def test_the_run_of_another_profile_cannot_take_the_answer(agent):
    scenario = SCENARIOS["pause_after_project_manager"]
    paused = runner(ScriptedLLM(**scenario["llm"]), agent).run("own_special", scenario["message"]).paused

    with pytest.raises(ProfileMismatch):
        runner(ScriptedLLM(), agent).run("special", "to Ana", paused=paused)


# ---------------------------------------------------------------- what the check refuses

def problems_of(**changes):
    agent, _ = assembled(("bad", lambda s: {**own_profile("chat", CHAT_STEPS, s), "name": "bad", **changes}))
    return " | ".join(agent.problems.get("profiles/bad", []))


def test_a_bad_step_name_is_a_problem_of_the_profile_not_an_exception_at_run_time():
    assert "unknown step 'no_such_step'" in problems_of(steps=["draft_writer", "no_such_step"])


def test_a_bad_hook_is_a_problem_of_the_profile():
    assert "unknown hook 'no_such_hook'" in problems_of(on_pause="no_such_hook")


def test_a_result_that_is_not_one_of_the_steps_is_a_problem_of_the_profile():
    assert "result_from 'triage_specialist' is not a step of the flow" in problems_of(result_from="triage_specialist")


def test_the_result_step_must_write_a_user_goal():
    found = problems_of(steps=["draft_writer", "safety_quality_gatekeeper"], inputs={"requires": ["user_goal", "task_category", "actions", "next_step"]})

    assert "the result step 'safety_quality_gatekeeper' does not write user_goal" in found


def test_a_step_that_reads_what_no_earlier_step_writes_is_a_problem_of_the_profile():
    assert "reads" in problems_of(steps=["editor_in_chief", "draft_writer"], inputs={"requires": []})


def test_an_empty_list_of_steps_is_a_problem_of_the_profile():
    assert "steps must be a list of steps" in problems_of(steps=[])


def test_a_profile_with_a_flow_and_steps_is_refused():
    assert "`flow` or `steps`, not both" in problems_of(flow="conversation")


def test_the_keys_of_an_own_flow_are_refused_in_a_profile_that_names_a_flow_file():
    agent, _ = assembled(("bad", lambda s: {**copy.deepcopy(s.profiles["chat"]), "name": "bad", "token_sha256": TOKEN, "result_from": "editor_in_chief"}))

    assert "result_from belongs to a profile that lists its own `steps`" in " ".join(agent.problems.get("profiles/bad", []))


def test_a_profile_with_a_problem_is_disabled_and_the_others_still_serve():
    agent, _ = assembled(("bad", lambda s: {**own_profile("chat", CHAT_STEPS, s), "name": "bad", "steps": ["draft_writer", "no_such_step"]}))

    assert "bad" in agent.disabled() and "chat" in agent.profiles and "bad" not in agent.profiles
