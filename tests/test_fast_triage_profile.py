# pyright: reportOptionalMemberAccess=false, reportArgumentType=false
"""T-08.11 (ADR-019): `dynamics_fast_triage`, the fast path for a client that sends only the message.

The triage first, then the three steps of `dynamics_fast` (all the profile's own steps, no flow file): three model calls and a code step.
"""
import os

import pytest

from application.assembly.assemble import assemble
from application.assembly.config_snapshot import build_snapshot
from application.runtime.profile.runner import ProfileRunner
from application.runtime.step.metrics import SessionMetrics
from infrastructure.outbound.config.file_source import FileConfigSource
from infrastructure.outbound.llm.shared.schemas.anthropic_schema import anthropic_schema_problems
from infrastructure.outbound.mcp.config.loader import load_tool_snapshot
from test_fast_flow import MCP_LIST, SELECTOR, WRITER, Tools, formats, selects, tool_action, writer_input, writes
from test_resume import CHECK, TRIAGE_ASKS, TRIAGE_OK, Script, _verdict
from test_flow_golden import TRIAGE, ScriptedLLM

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
NAME = "dynamics_fast_triage"


@pytest.fixture(scope="module")
def agent():
    built = assemble(build_snapshot(FileConfigSource(PROJECT_ROOT)), mcp_servers=load_tool_snapshot(),
                     schema_rules={"anthropic": anthropic_schema_problems})
    built.raise_on_errors()
    return built


def run(agent, selection, tools, triage=None, message="the orders of C-1"):
    llm = ScriptedLLM(overrides={TRIAGE: triage or TRIAGE_OK, SELECTOR: selection, WRITER: writes()})
    runner = ProfileRunner(llm, MCP_LIST, SessionMetrics(), tools, agent)
    return runner.run(NAME, message), llm, runner



def test_the_profile_is_the_triage_and_the_three_steps_and_needs_no_inputs(agent):
    profile = agent.profile(NAME)

    assert profile.steps == ["triage_specialist", "tool_selector", "tool_caller", "answer_writer"]
    assert profile.requires == [] and profile.flow_name is None      # its own steps: no flow file


def test_a_message_alone_is_answered_by_the_triage_the_selector_the_caller_and_the_writer(agent):
    tools = Tools()

    result, llm, _ = run(agent, selects(tool_action()), tools)

    assert formats(llm) == [TRIAGE, SELECTOR, WRITER]
    assert tools.calls == [("read_orders", {"customer_no": "C-1"})]
    assert result.reply == "the reply" and result.paused is None
    assert "SO-2|Open" in writer_input(llm)


def test_it_shares_the_models_the_tools_and_the_prompts_of_dynamics_fast(agent):
    fast, triage = agent.profile("dynamics_fast"), agent.profile(NAME)

    assert triage.definition["tools"] == fast.definition["tools"] and triage.definition["models"] == fast.definition["models"]
    assert {k: v.append for k, v in triage.prompts.items()} == {k: v.append for k, v in fast.prompts.items()}


def test_a_missing_value_pauses_at_the_triage_and_the_answer_resumes_it(agent):
    tools = Tools()
    paused, llm, _ = run(agent, selects(tool_action()), tools, triage=TRIAGE_ASKS)

    assert paused.paused is not None and tools.calls == [] and SELECTOR not in formats(llm)

    again = ProfileRunner(ScriptedLLM(overrides={CHECK: Script(_verdict("answered", "C-1")), TRIAGE: TRIAGE_OK,
                                                 SELECTOR: selects(tool_action()), WRITER: writes()}),
                          MCP_LIST, SessionMetrics(), tools, agent)
    resumed = again.run(NAME, "C-1", paused=paused.paused)

    assert resumed.paused is None and resumed.reply == "the reply" and len(tools.calls) == 1
