# pyright: reportOptionalMemberAccess=false, reportOptionalSubscript=false, reportOptionalIterable=false, reportArgumentType=false
"""
What objects the flow creates and how it completes them, step by step. Made for debugging.

Two objects matter:
- the `Response` that the mapper builds from each LLM answer (only the fields of that phase are filled);
- the `FlowState`, the object that is completed along the flow: each step writes some fields into it.

The main test fixes, for every step, which state fields are SET (first filled), CHG (overwritten),
= (kept) or . (still empty). When it fails, the message contains the full report of that step:
the input sent, the raw JSON answer, the Response object, what the mapper ignored, and the state after it.

To look at a flow yourself:
    windows/Scripts/python.exe tests/manual/debug_flow.py --list
    windows/Scripts/python.exe tests/manual/debug_flow.py --scenario=full_path_with_mcp --print --interactive

Nothing is printed. The results are SAVED to files in tests/output/flow_trace/<scenario>/ every time
the tests run (or in the folder of the FLOW_TRACE_DIR variable): one markdown file per LLM call, an index,
and report.md with the whole step-by-step report. When a test fails, the report of the failing step is saved
in tests/output/flow_trace/failures/ and the failure message only gives its path.
"""
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flow_trace import STATE_FIELDS, StopTrace, format_matrix, format_step, trace_flow, write_report
from test_flow_golden import MCP_LIST, SCENARIOS, ScriptedLLM, _action, _plan


@pytest.fixture(autouse=True)
def _project_cwd(monkeypatch):
    monkeypatch.chdir(PROJECT_ROOT)


def output_dir():
    """Where the trace files are saved: FLOW_TRACE_DIR, or tests/output/flow_trace (ignored by git)."""
    return os.environ.get("FLOW_TRACE_DIR") or os.path.join(PROJECT_ROOT, "tests", "output", "flow_trace")


def traces_of(name, scenario=None):
    scenario = scenario or SCENARIOS[name]
    return trace_flow(scenario["message"], ScriptedLLM(**scenario["llm"]), MCP_LIST)


def run(name):
    return {t.step: t for t in traces_of(name)}


@pytest.fixture
def full():
    return run("full_path_with_mcp")


# ===============================================
#  THE CONTRACT: HOW EACH STEP COMPLETES THE STATE
# ===============================================

def marks(**changes):
    """Every field is '.' (empty) unless the case says otherwise."""
    result = {name: "." for name in STATE_FIELDS}
    result.update(changes)
    return result


# scenario -> step -> the mark of every state field after that step
EXPECTED = {
    "full_path_with_mcp": {
        "triage_specialist":         marks(intent="SET", user_goal="SET", task_category="SET", next_step="SET"),
        "project_manager":           marks(intent="=", user_goal="=", task_category="=", actions="SET", next_step="CHG"),
        "safety_quality_gatekeeper": marks(intent="=", user_goal="=", task_category="=", actions="=", next_step="CHG",
                                           safety_and_validation="SET"),
        "action_executor":           marks(intent="=", user_goal="=", task_category="=", actions="CHG", next_step="=",
                                           safety_and_validation="="),
        "draft_writer":              marks(intent="=", user_goal="CHG", task_category="=", actions="=", next_step="=",
                                           safety_and_validation="="),
        "editor_in_chief":           marks(intent="=", user_goal="CHG", task_category="=", actions="=", next_step="CHG",
                                           safety_and_validation="="),
    },
    "no_actions": {                 # the plan is an empty list: the flow object keeps `actions` empty
        "triage_specialist":         marks(intent="SET", user_goal="SET", task_category="SET", next_step="SET"),
        "project_manager":           marks(intent="=", user_goal="=", task_category="=", next_step="CHG"),
        "safety_quality_gatekeeper": marks(intent="=", user_goal="=", task_category="=", next_step="CHG",
                                           safety_and_validation="SET"),
        "action_executor":           marks(intent="=", user_goal="=", task_category="=", next_step="=",
                                           safety_and_validation="="),          # nothing to execute: nothing changes
        "draft_writer":              marks(intent="=", user_goal="CHG", task_category="=", next_step="=",
                                           safety_and_validation="="),
        "editor_in_chief":           marks(intent="=", user_goal="CHG", task_category="=", next_step="CHG",
                                           safety_and_validation="="),
    },
    "pause_after_project_manager": {
        "triage_specialist": marks(intent="SET", user_goal="SET", task_category="SET", next_step="SET"),
        "project_manager":   marks(intent="=", user_goal="=", task_category="=", actions="SET", next_step="CHG"),
        "user_question":     marks(intent="=", user_goal="=", task_category="=", actions="=", next_step="="),
    },
    "pause_after_triage": {
        "triage_specialist": marks(intent="SET", user_goal="SET", task_category="SET", next_step="SET"),
        "user_question":     marks(intent="=", user_goal="=", task_category="=", next_step="="),
    },
    "pause_after_gatekeeper": {
        "triage_specialist":         marks(intent="SET", user_goal="SET", task_category="SET", next_step="SET"),
        "project_manager":           marks(intent="=", user_goal="=", task_category="=", actions="SET", next_step="CHG"),
        "safety_quality_gatekeeper": marks(intent="=", user_goal="=", task_category="=", actions="=", next_step="CHG",
                                           safety_and_validation="SET"),
        "user_question":             marks(intent="=", user_goal="=", task_category="=", actions="=", next_step="=",
                                           safety_and_validation="="),
    },
}

CASES = [(scenario, step) for scenario, steps in EXPECTED.items() for step in steps]


@pytest.mark.parametrize("scenario,step", CASES, ids=[f"{s}:{t}" for s, t in CASES])
def test_a_step_completes_the_state_as_expected(scenario, step):
    traces = traces_of(scenario)
    by_step = {t.step: t for t in traces}
    assert list(by_step) == list(EXPECTED[scenario]), (
        "the steps that ran are not the expected ones\n\n" + format_matrix(traces))

    actual = by_step[step].marks
    if actual != EXPECTED[scenario][step]:
        wrong = {f: (EXPECTED[scenario][step][f], actual[f]) for f in STATE_FIELDS
                 if actual[f] != EXPECTED[scenario][step][f]}
        report = os.path.join(output_dir(), "failures", f"{scenario}__{step}.md")
        write_report(traces, report, f"{scenario}: {step}")
        pytest.fail(f"scenario {scenario!r}, step {step!r}: fields with a different mark "
                    f"(expected, actual): {wrong}. Full report saved in {report}")


# ===============================================
#  WHAT THE STEP WROTE (THE VALUES)
# ===============================================

class TestValuesWritten:
    def test_triage_starts_the_state(self, full):
        assert set(full["triage_specialist"].changed) == {"intent", "user_goal", "task_category", "next_step"}
        assert all(before is None for before, _ in full["triage_specialist"].changed.values())

    def test_the_planner_adds_the_actions_and_replaces_next_step(self, full):
        changed = full["project_manager"].changed
        assert [a["id"] for a in changed["actions"][1]] == ["a1", "a2"]
        assert changed["actions"][1][1]["dependencies"] == ["a1"]
        assert changed["next_step"][0]["recommended_action"] == "plan"       # triage's, replaced
        assert changed["next_step"][1]["recommended_action"] == "go"

    def test_the_planner_complexity_does_not_reach_the_state(self, full):
        assert "task_category" not in full["project_manager"].changed

    def test_the_gate_adds_the_safety(self, full):
        assert full["safety_quality_gatekeeper"].changed["safety_and_validation"][1] == {
            "sensitive": False, "requires_confirmation": False}

    def test_the_executor_fills_outputs_inside_the_actions(self, full):
        before, after = full["action_executor"].changed["actions"]
        assert [a["output"] for a in before] == [None, None]
        assert [a["output"] for a in after] == ["out-p4-a1", "out-p6-a2"]     # a2 was cleaned by the data engineer

    def test_the_draft_replaces_the_goal_and_the_editor_writes_the_final_text(self, full):
        assert full["draft_writer"].changed["user_goal"][1] == {"summary": "s", "expected_outcome": "draft answer"}
        assert full["editor_in_chief"].changed["user_goal"][1]["expected_outcome"] == "final answer"
        assert full["editor_in_chief"].changed["next_step"][1]["status"] == "complete"

    def test_the_status_of_next_step_along_the_flow(self, full):
        assert [t.state["next_step"]["status"] for t in full.values()] == \
            ["proceed", "proceed", "proceed", "proceed", "proceed", "complete"]

    def test_fields_nobody_writes_stay_empty(self, full):
        last = list(full.values())[-1].state
        for name in ("constraints", "mcp_routing", "missing_information", "answers"):
            assert last[name] is None

    def test_the_intent_is_written_once(self, full):
        assert [n for n, t in full.items() if "intent" in t.changed] == ["triage_specialist"]


# ===============================================
#  FROM RAW JSON TO THE RESPONSE OBJECT
# ===============================================

class TestResponseObjects:
    """The mapper fills only what the LLM answered, and it tells what it did not use."""

    @pytest.mark.parametrize("step,filled", [
        ("triage_specialist", ["intent", "user_goal", "task_category", "next_step"]),
        ("project_manager", ["actions", "next_step"]),
        ("safety_quality_gatekeeper", ["safety_and_validation", "next_step"]),
        ("draft_writer", ["user_goal"]),
        ("editor_in_chief", ["user_goal", "next_step"]),
    ])
    def test_a_phase_fills_only_its_own_fields(self, full, step, filled):
        assert [c.filled for c in full[step].calls] == [filled]

    def test_the_action_calls_answer_with_actions_only(self, full):
        assert [c.filled for c in full["action_executor"].calls] == [["actions"]] * 3

    def test_every_call_records_its_input_and_the_raw_json(self, full):
        call = full["project_manager"].calls[0]
        assert call.model == "gpt-4.1" and call.system_prompt_chars > 1000
        assert call.user_message.startswith("{'user_goal':")
        assert set(call.raw) == {"actions", "next_step", "task_category_complexity"}

    def test_the_planners_complexity_is_reported_as_not_read(self, full):
        assert full["project_manager"].calls[0].ignored == ["task_category_complexity"]

    def test_empty_values_of_the_json_are_none_in_the_object(self, full):
        call = full["project_manager"].calls[0]
        assert call.raw["next_step"]["blocking_reason"] == ""                 # what the LLM wrote
        assert call.response["next_step"]["blocking_reason"] is None          # what the object holds
        assert call.raw["actions"][0]["dependencies"] == [] and call.response["actions"][0]["dependencies"] is None

    def test_an_mcp_context_without_arguments_is_not_kept_in_the_object(self):
        action = _action("1", "mcp_tool_call")
        action["mcp_context"]["parameters"] = {}
        scenario = {"message": "hi", "llm": {"overrides": {
            "project_manager_phase2_response_format": _plan(action)}}}
        call = {t.step: t for t in traces_of(None, scenario)}["project_manager"].calls[0]
        assert call.raw["actions"][0]["mcp_context"]["server_id"] == "aws_microservice"     # the LLM wrote it
        assert call.response["actions"][0]["mcp_context"] is None                            # the object does not have it

    def test_nested_subactions_are_kept_in_the_object(self):
        actions = run("action_with_subactions")["project_manager"].calls[0].response["actions"]
        assert list(actions[0]["subactions"]) == ["1.1", "1.2"]

    def test_a_question_for_the_user_is_a_text_only_response(self):
        last = traces_of("pause_after_project_manager")[-1]
        assert last.step == "user_question" and last.calls[0].filled == ["text"]
        assert last.calls[0].text == "Please tell me the missing details."


# ===============================================
#  OTHER PATHS
# ===============================================

class TestOtherPaths:
    def test_subactions_are_inside_their_parent_and_all_get_outputs(self):
        after = run("action_with_subactions")["action_executor"].state["actions"]
        assert list(after[0]["subactions"]) == ["1.1", "1.2"]
        assert after[0]["output"] and all(s["output"] for s in after[0]["subactions"].values())
        assert after[1]["dependencies"] == ["1"] and after[1]["output"]

    def test_a_failed_tool_leaves_an_error_and_skips_its_dependents(self):
        after = run("mcp_tool_fails_then_dependents_are_skipped")["action_executor"].state["actions"]
        assert after[0]["output"] is None and after[0]["error"] == "tool unavailable"
        assert after[1]["output"] is None and "skipped" in after[1]["error"]
        assert after[2]["output"] and after[2]["error"] is None

    def test_blocked_mcp_actions_get_the_confirmation_error(self):
        after = run("mcp_blocked_by_confirmation")["action_executor"].state["actions"]
        assert "confirmation" in after[1]["error"]

    def test_a_pause_ends_the_trace_with_the_question(self):
        traces = run("pause_after_project_manager")
        assert list(traces) == ["triage_specialist", "project_manager", "user_question"]
        step = traces["project_manager"].state["next_step"]
        assert step["status"] == "awaiting_user_input" and step["requested_user_input"] == ["who is the recipient?"]


# ===============================================
#  THE DEBUGGING TOOL ITSELF
# ===============================================

class TestTheTool:
    def test_the_report_of_a_step_has_every_section(self, full):
        text = format_step(full["project_manager"])
        for part in ("STEP 2: project_manager", "LLM call", "INPUT (user message)", "RAW ANSWER",
                     "RESPONSE OBJECT: Response(actions, next_step)",
                     "not read by the mapper: task_category_complexity",
                     "HOW THE FLOW OBJECT WAS COMPLETED BY THIS STEP", "actions SET", "next_step CHANGED",
                     "FLOW OBJECT AFTER THIS STEP"):
            assert part in text

    def test_the_matrix_lists_every_field_and_step(self, full):
        text = format_matrix(list(full.values()))
        assert all(name in text for name in STATE_FIELDS)
        assert "1=triage_specialist" in text and "6=editor_in_chief" in text

    def test_a_callback_can_end_the_trace_after_a_step(self):
        seen = []

        def on_step(trace):
            seen.append(trace.step)
            if trace.index == 2:
                raise StopTrace()

        scenario = SCENARIOS["full_path_with_mcp"]
        traces = trace_flow(scenario["message"], ScriptedLLM(**scenario["llm"]), MCP_LIST, on_step)
        assert seen == ["triage_specialist", "project_manager"] and len(traces) == 2

    def test_the_report_is_saved_in_a_file_and_nothing_is_printed(self, full, tmp_path, capsys):
        path = write_report(list(full.values()), str(tmp_path / "report.md"), "full path")
        text = open(path, encoding="utf-8").read()
        assert "STATE COMPLETION" in text and "STEP 2/6: project_manager" in text
        assert "RAW ANSWER" in text and "HOW THE FLOW OBJECT WAS COMPLETED BY THIS STEP" in text
        printed = capsys.readouterr().out
        assert "STEP " not in printed and "STATE COMPLETION" not in printed


# ===============================================
#  ONE MARKDOWN FILE PER MODIFICATION (test tooling only)
# ===============================================

import json  # noqa: E402
import re  # noqa: E402

from flow_trace import trace_to_markdown  # noqa: E402


def write_files(name, tmp_path):
    scenario = SCENARIOS[name]
    paths = trace_to_markdown(scenario["message"], ScriptedLLM(**scenario["llm"]), str(tmp_path), MCP_LIST, name)
    return {os.path.basename(p): open(p, encoding="utf-8").read() for p in paths}


def last_json_block(markdown):
    return json.loads(re.findall(r"```json\n(.*?)\n```", markdown, re.S)[-1])


class TestMarkdownFiles:
    def test_one_file_per_llm_call_plus_an_index(self, tmp_path):
        files = write_files("full_path_with_mcp", tmp_path)
        assert list(files) == [
            "01_triage_specialist_phase1.md", "02_project_manager_phase2.md", "03_safety_quality_gatekeeper_phase3.md",
            "04_action_executor_phase4.md", "05_action_executor_phase5.md", "06_action_executor_phase6.md",
            "07_draft_writer_phase7.md", "08_editor_in_chief_phase8.md"]
        index = (tmp_path / "00_index.md").read_text(encoding="utf-8")
        assert index.count("](") == 8 and "actions, next_step" in index

    def test_the_request_is_at_the_top_and_the_full_object_at_the_bottom(self, tmp_path):
        text = write_files("full_path_with_mcp", tmp_path)["02_project_manager_phase2.md"]
        headings = re.findall(r"^## (.*)$", text, re.M)
        assert headings[0].startswith("1. Request sent to the LLM")
        assert headings[-1].startswith("6. Full object of the flow after the data was loaded")
        assert [h.split(".")[0] for h in headings] == ["1", "2", "3", "4", "5", "6"]

    def test_the_top_holds_what_was_sent(self, tmp_path):
        text = write_files("full_path_with_mcp", tmp_path)["02_project_manager_phase2.md"]
        top = text.split("## 2.")[0]
        assert "model: `gpt-4.1`" in top and "response format: `project_manager_phase2_response_format`" in top
        assert "'available_mcp_servers'" in top                 # the user message
        assert "You are the PROJECT MANAGER." in top           # the system message
        assert '"$defs"' in top                                # the JSON schema

    def test_the_bottom_is_the_whole_object_after_the_data_was_loaded(self, tmp_path):
        text = write_files("full_path_with_mcp", tmp_path)["02_project_manager_phase2.md"]
        bottom = last_json_block(text)
        assert bottom["message"] == "what is the weather"
        assert [a["id"] for a in bottom["actions"]] == ["a1", "a2"]      # loaded by this call
        assert bottom["intent"]["primary"] == "information_request"      # kept from triage
        assert bottom["safety_and_validation"] is None                   # not filled yet

    def test_each_file_shows_only_what_had_been_loaded_up_to_that_call(self, tmp_path):
        files = write_files("full_path_with_mcp", tmp_path)
        assert last_json_block(files["01_triage_specialist_phase1.md"])["actions"] is None
        assert last_json_block(files["02_project_manager_phase2.md"])["actions"] is not None
        assert last_json_block(files["02_project_manager_phase2.md"])["safety_and_validation"] is None
        assert last_json_block(files["03_safety_quality_gatekeeper_phase3.md"])["safety_and_validation"] is not None

    def test_a_tool_action_is_shown_raw_and_then_cleaned_in_two_files(self, tmp_path):
        files = write_files("full_path_with_mcp", tmp_path)
        def output_of_a2(name):
            return last_json_block(files[name])["actions"][1]["output"]
        assert output_of_a2("04_action_executor_phase4.md") is None          # only a1 had run
        assert output_of_a2("05_action_executor_phase5.md") == "out-p5-a2"   # the raw result of the tool
        assert output_of_a2("06_action_executor_phase6.md") == "out-p6-a2"   # cleaned by the data engineer

    def test_the_section_that_lists_changes_names_the_fields(self, tmp_path):
        files = write_files("full_path_with_mcp", tmp_path)
        text = files["02_project_manager_phase2.md"]
        assert "**actions**: SET" in text and "**next_step**: CHANGED" in text
        assert "Not read by the mapper:** `task_category_complexity`" in text
        assert "**user_goal**: CHANGED" in files["07_draft_writer_phase7.md"]

    def test_the_raw_answer_is_the_json_the_llm_returned(self, tmp_path):
        text = write_files("full_path_with_mcp", tmp_path)["03_safety_quality_gatekeeper_phase3.md"]
        raw = json.loads(re.findall(r"```json\n(.*?)\n```", text.split("## 2.")[1].split("## 3.")[0], re.S)[0])
        assert raw["safety_and_validation"] == {"sensitive": False, "requires_confirmation": False}

    def test_the_question_for_the_user_gets_its_own_file_without_changes(self, tmp_path):
        files = write_files("pause_after_project_manager", tmp_path)
        assert list(files) == ["01_triage_specialist_phase1.md", "02_project_manager_phase2.md", "03_user_question_text.md"]
        question = files["03_user_question_text.md"]
        assert "Please tell me the missing details." in question
        assert "Nothing." in question.split("## 5.")[1].split("## 6.")[0]
        assert last_json_block(question)["next_step"]["status"] == "awaiting_user_input"

    def test_a_flow_without_actions_has_no_executor_files(self, tmp_path):
        assert not [n for n in write_files("no_actions", tmp_path) if "action_executor" in n]

    def test_the_report_of_a_scenario_is_saved_next_to_its_files(self, tmp_path):
        write_files("full_path_with_mcp", tmp_path)
        report = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "STEP 6/6: editor_in_chief" in report and "STATE COMPLETION" in report

    def test_the_trace_of_every_scenario_is_saved(self, capsys):
        """Runs on every test run. The files are in tests/output/flow_trace/<scenario>/ (or FLOW_TRACE_DIR)."""
        for name in SCENARIOS:
            folder = os.path.join(output_dir(), name)
            assert write_files(name, folder), name
            assert os.path.exists(os.path.join(folder, "report.md")) and os.path.exists(os.path.join(folder, "00_index.md"))
        printed = capsys.readouterr().out                     # the app's own log lines may appear, the trace must not
        assert "STEP " not in printed and "RAW ANSWER" not in printed and "STATE COMPLETION" not in printed


# ===============================================
#  DEBUGGING EACH PART: PROBLEMS, ONE STEP ALONE, RUNS COMPARED
# ===============================================

from flow_trace import (compare_runs, load_state, problems_of, save_step_inputs, step_names,  # noqa: E402
                        trace_step, write_compare)
from application.orchestration.support.schemas import object_schema, property_schema  # noqa: E402

NEXT_STEP_SCHEMA = object_schema(["next_step"], {"next_step": property_schema("next_step")})
GOOD_STEP = {"next_step": {"ready_to_execute": True, "status": "proceed", "recommended_action": ""}}


class TestProblemsInAnAnswer:
    def test_a_valid_answer_has_no_problems(self):
        assert problems_of(GOOD_STEP, NEXT_STEP_SCHEMA) == []

    def test_a_missing_required_key_is_reported(self):
        answer = {"next_step": {"ready_to_execute": True, "status": "proceed"}}
        assert any("'recommended_action' is a required property" in p for p in problems_of(answer, NEXT_STEP_SCHEMA))

    def test_a_key_the_schema_does_not_have_is_reported(self):
        answer = {"next_step": {**GOOD_STEP["next_step"], "request_user_input": ["what?"]}}    # the old spelling
        assert any("request_user_input" in p for p in problems_of(answer, NEXT_STEP_SCHEMA))

    def test_a_value_outside_the_allowed_ones_is_reported(self):
        answer = {"next_step": {**GOOD_STEP["next_step"], "status": "maybe"}}
        problems = problems_of(answer, NEXT_STEP_SCHEMA)
        assert any(p.startswith("schema: next_step/status") and "'maybe' is not one of" in p for p in problems)

    def test_a_wrong_type_is_reported_with_its_path(self):
        answer = {"next_step": {**GOOD_STEP["next_step"], "ready_to_execute": "yes"}}
        assert any(p.startswith("schema: next_step/ready_to_execute") for p in problems_of(answer, NEXT_STEP_SCHEMA))

    def test_an_answer_that_is_not_an_object_is_reported(self):
        problems = problems_of(None, NEXT_STEP_SCHEMA, "Sure! Here you go")
        assert problems and problems[0].startswith("answer: ")

    def test_a_text_answer_without_a_schema_is_not_a_problem(self):
        assert problems_of(None, None, "Hello!") == []

    def test_a_literal_backslash_n_is_reported(self):
        answer = {"user_goal": {"summary": "s", "expected_outcome": "| a |\\n| b |"}}
        problems = problems_of(answer, None)
        assert problems == ["text: user_goal.expected_outcome holds a literal backslash-n instead of a line break"]

    def test_a_real_line_break_is_not_a_problem(self):
        assert problems_of({"user_goal": {"expected_outcome": "| a |\n| b |"}}, None) == []

    def test_a_schema_that_cannot_be_checked_is_reported_not_raised(self):
        problems = problems_of({"a": 1}, {"type": "object", "properties": {"a": {"$ref": "#/nowhere"}}})
        assert problems and problems[0].startswith("schema:")

    def test_the_scripted_answers_of_the_scenarios_are_valid(self):
        for name in SCENARIOS:
            if name not in ("no_actions", "pause_without_details"):      # these model an empty plan, see the next test
                assert [p for t in traces_of(name) for p in t.problems] == [], name

    def test_an_empty_plan_is_reported_because_the_schema_asks_for_at_least_one_action(self):
        problems = [p for t in traces_of("no_actions") for p in t.problems]
        assert problems == ["project_manager_phase2_response_format: schema: actions: [] should be non-empty"]

    def test_a_bad_answer_shows_up_in_the_call_the_step_and_the_files(self, tmp_path):
        bad = {"next_step": {"ready_to_execute": True, "status": "maybe", "recommended_action": ""},
               "safety_and_validation": {"sensitive": False, "requires_confirmation": False}}
        scenario = {"message": "hi", "llm": {"overrides": {
            "safety_quality_gatekeeper_phase3_response_format": bad}}}
        mods, failures = [], []
        traces = trace_flow("hi", ScriptedLLM(**scenario["llm"]), MCP_LIST, modifications=mods, failures=failures)

        # the mapper rejects the status, so the step is tried again and then the flow fails: all of it is kept
        gate_calls = [m for m in mods if m.step == "safety_quality_gatekeeper"]
        assert len(gate_calls) == 3                                            # AI_AGENT_MAX_ATTEMPTS
        assert all(m.call.error and "status must be one of" in m.call.error for m in gate_calls)
        assert all(m.call.raw == bad for m in gate_calls)                     # the raw answer is not lost
        assert any("'maybe' is not one of" in p for p in gate_calls[0].call.problems)
        assert [t.step for t in traces] == ["triage_specialist", "project_manager"]      # the failed step has no result
        assert len(failures) == 1 and "bad_answer" in str(failures[0])

        paths = trace_to_markdown("hi", ScriptedLLM(**scenario["llm"]), str(tmp_path), MCP_LIST)
        md = open([p for p in paths if "phase3" in p][0], encoding="utf-8").read()
        assert "## 3. Problems found in the answer (" in md and "'maybe' is not one of" in md
        assert "**NOT BUILT.**" in md and "Nothing was loaded into the flow object by this call." in md
        assert "| " in (tmp_path / "00_index.md").read_text(encoding="utf-8")
        report = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "THE FLOW FAILED: AgentFailure" in report and "'maybe' is not one of" in report


class TestOneStepAlone:
    def _states(self, tmp_path):
        traces = traces_of("full_path_with_mcp")
        save_step_inputs(traces, str(tmp_path))
        return {name: str(tmp_path / "states" / f"{i + 1:02d}_{name}.pkl")
                for i, name in enumerate([t.step for t in traces])}

    def test_the_steps_are_the_real_ones(self):
        assert step_names(MCP_LIST) == ["triage_specialist", "project_manager", "safety_quality_gatekeeper",
                                        "action_executor", "draft_writer", "editor_in_chief"]

    def test_the_input_of_every_step_is_saved(self, tmp_path):
        assert len(self._states(tmp_path)) == 6
        assert all(os.path.exists(p) for p in self._states(tmp_path).values())

    def test_a_saved_input_is_what_the_step_received(self, tmp_path):
        state = load_state(self._states(tmp_path)["project_manager"])
        assert state.user_goal is not None and state.actions is None       # after triage, before the plan

    def test_one_step_runs_alone_with_the_real_code(self, tmp_path):
        state = load_state(self._states(tmp_path)["project_manager"])
        scenario = SCENARIOS["full_path_with_mcp"]
        mods, after, waiting = trace_step("project_manager", state, ScriptedLLM(**scenario["llm"]), MCP_LIST)
        assert [m.call.format_name for m in mods] == ["project_manager_phase2_response_format"]
        assert [a.id.get_value() for a in after.actions] == ["a1", "a2"]
        assert waiting is False
        assert set(mods[0].changes) == {"actions", "next_step"}

    def test_the_saved_input_is_not_changed_by_running_the_step(self, tmp_path):
        state = load_state(self._states(tmp_path)["project_manager"])
        trace_step("project_manager", state, ScriptedLLM(), MCP_LIST)
        assert state.actions is None

    def test_a_step_that_leaves_the_flow_waiting_says_so(self, tmp_path):
        state = load_state(self._states(tmp_path)["project_manager"])
        scenario = SCENARIOS["pause_after_project_manager"]
        _, after, waiting = trace_step("project_manager", state, ScriptedLLM(**scenario["llm"]), MCP_LIST)
        assert waiting is True and after.next_step.status.get_value() == "awaiting_user_input"

    def test_an_unknown_step_lists_the_real_ones(self, tmp_path):
        state = load_state(self._states(tmp_path)["project_manager"])
        with pytest.raises(KeyError, match="triage_specialist"):
            trace_step("nope", state, ScriptedLLM(), MCP_LIST)

    def test_the_action_executor_runs_alone_on_a_saved_plan(self, tmp_path):
        state = load_state(self._states(tmp_path)["action_executor"])
        mods, after, _ = trace_step("action_executor", state, ScriptedLLM(), MCP_LIST)
        assert [m.call.format_name.split("_")[0] for m in mods] == ["phase4", "phase5", "phase6"]
        assert all(a.output is not None for a in after.actions)


class TestComparingRuns:
    class Varying(ScriptedLLM):
        """Answers the triage differently every time."""
        count = 0

        def ask(self, Payload):
            if Payload.response_format and Payload.response_format.name.startswith("triage"):
                type(self).count += 1
                self.overrides = {Payload.response_format.name: {
                    "intent": {"primary": "information_request", "secondary": [], "confidence": 0.9},
                    "user_goal": {"summary": f"summary {self.count % 2}", "expected_outcome": "o"},
                    "task_category": {"domain": "system", "type": "analysis", "complexity": "low"},
                    "next_step": {"ready_to_execute": True, "status": "proceed", "recommended_action": ""}}}
            return super().ask(Payload)

    def _runs(self, tmp_path, llm_class, times=3):
        traces = traces_of("full_path_with_mcp")
        save_step_inputs(traces, str(tmp_path))
        state = load_state(str(tmp_path / "states" / "01_triage_specialist.pkl"))
        return [trace_step("triage_specialist", state, llm_class(), MCP_LIST)[0] for _ in range(times)]

    def test_runs_that_agree_are_marked_so(self, tmp_path):
        text = compare_runs(self._runs(tmp_path, ScriptedLLM), "triage")
        assert "3 runs, same input." in text
        assert "| `user_goal` | yes |" in text and "differs" not in text

    def test_runs_that_differ_show_each_value(self, tmp_path):
        text = compare_runs(self._runs(tmp_path, self.Varying), "triage")
        assert "| `user_goal` | **NO** |" in text and "| `intent` | yes |" in text
        assert "### `user_goal` differs" in text and "summary 0" in text and "summary 1" in text

    def test_the_comparison_lists_the_problems_of_every_run(self, tmp_path):
        class Bad(ScriptedLLM):
            def ask(self, Payload):
                if Payload.response_format and Payload.response_format.name.startswith("triage"):
                    self.overrides = {Payload.response_format.name: {
                        "intent": {"primary": "information_request", "secondary": [], "confidence": 0.9},
                        "user_goal": {"summary": "s", "expected_outcome": "o"},
                        "task_category": {"domain": "system", "type": "analysis", "complexity": "low"},
                        "next_step": {"ready_to_execute": True, "status": "maybe", "recommended_action": ""}}}
                return super().ask(Payload)
        text = compare_runs(self._runs(tmp_path, Bad, 2))
        assert "### Problems seen" in text and "'maybe' is not one of" in text

    def test_the_comparison_is_saved_in_a_file(self, tmp_path):
        path = write_compare(self._runs(tmp_path, ScriptedLLM, 2), str(tmp_path / "x" / "compare.md"), "triage")
        assert open(path, encoding="utf-8").read().startswith("# Runs of the same step compared: triage")


# ===============================================
#  STOPPING IN A DEBUGGER AT THE START OF THE STEPS AND WHERE THE RESPONSE IS ALLOCATED
# ===============================================

import builtins  # noqa: E402

from flow_trace import STOP_POINTS, run_with_stops  # noqa: E402


class Stops:
    """Records every stop, and what the state looked like at that moment."""

    def __init__(self):
        self.stops = []

    def __call__(self, kind, step=None, state=None, payload=None, response=None, action=None, phase_id=None):
        self.stops.append({
            "kind": kind, "step": step, "phase": phase_id,
            "action": action.id.get_value() if action is not None else None,
            "actions_in_state": state.actions is not None if state is not None else None,
            "response_fields": sorted(k for k in ("actions", "next_step", "user_goal") if response is not None
                                      and getattr(response, k) is not None),
            "has_request": payload is not None,
            "raw": response.raw if response is not None else None,
        })

    def kinds(self, step=None):
        return [(s["kind"], s["step"]) for s in self.stops if step is None or s["step"] == step]


def run_stops(name="full_path_with_mcp", **kwargs):
    scenario = SCENARIOS[name]
    stops = Stops()
    result = run_with_stops(scenario["message"], ScriptedLLM(**scenario["llm"]), MCP_LIST, stop=stops, **kwargs)
    return stops, result


class TestStops:
    def test_the_stop_points(self):
        assert STOP_POINTS == ("start", "response", "loaded")

    def test_every_step_stops_at_its_start_and_when_its_data_is_loaded(self):
        stops, _ = run_stops(at=("start", "loaded"))
        steps = ["triage_specialist", "project_manager", "safety_quality_gatekeeper", "action_executor",
                 "draft_writer", "editor_in_chief"]
        assert [s["step"] for s in stops.stops if s["kind"] == "start"] == steps
        assert [s["step"] for s in stops.stops if s["kind"] == "loaded" and s["action"] is None] == steps

    def test_the_order_of_the_stops_of_one_step(self):
        stops, _ = run_stops(at=("start", "response", "loaded"))
        assert [k for k, _ in stops.kinds("project_manager")] == ["start", "response", "loaded"]

    def test_at_the_response_the_object_exists_but_the_state_does_not_have_it_yet(self):
        stops, _ = run_stops(at=("start", "response", "loaded"))
        by_kind = {s["kind"]: s for s in stops.stops if s["step"] == "project_manager"}
        assert by_kind["start"]["actions_in_state"] is False
        assert by_kind["response"]["actions_in_state"] is False          # allocated in the Response, not loaded
        assert by_kind["response"]["response_fields"] == ["actions", "next_step"]
        assert by_kind["response"]["has_request"] and set(by_kind["response"]["raw"]) >= {"actions", "next_step"}
        assert by_kind["loaded"]["actions_in_state"] is True             # now it is in the state

    def test_there_is_a_response_stop_for_every_llm_call(self):
        stops, _ = run_stops(at=("response",))
        assert [s["phase"] for s in stops.stops] == [1, 2, 3, 4, 5, 6, 7, 8]

    def test_the_action_executor_stops_after_each_action_gets_its_result(self):
        stops, _ = run_stops(at=("loaded",))
        assert [s["action"] for s in stops.stops if s["step"] == "action_executor" and s["action"]] == ["a1", "a2"]

    def test_only_the_chosen_steps_stop(self):
        stops, _ = run_stops(at=("start", "response", "loaded"), steps=["project_manager"])
        assert {s["step"] for s in stops.stops} == {"project_manager"}

    def test_the_flow_result_is_the_normal_one(self):
        _, result = run_stops(at=("start", "response", "loaded"))
        assert result.reply == "final answer" and result.paused is None

    def test_an_unknown_stop_point_is_an_error(self):
        with pytest.raises(ValueError, match="unknown stop points"):
            run_with_stops("hi", ScriptedLLM(), MCP_LIST, at=("middle",), stop=Stops())

    def test_the_real_code_is_left_as_it_was(self):
        from application.orchestration.flows.action_executor import ActionExecutor
        from application.orchestration.engine.phase_runner import PhaseRunner
        send, succeed = PhaseRunner.send, ActionExecutor.__dict__["_succeed"]
        run_stops(at=("start", "response", "loaded"))
        assert PhaseRunner.send is send and ActionExecutor.__dict__["_succeed"] is succeed

    def test_a_stop_can_read_the_flow_object(self):
        from flow_trace import snapshot
        seen = []

        def stop(kind, step=None, state=None, **rest):
            if kind == "loaded" and step == "editor_in_chief":
                seen.append(snapshot(state)["user_goal"]["expected_outcome"])

        scenario = SCENARIOS["full_path_with_mcp"]
        run_with_stops(scenario["message"], ScriptedLLM(**scenario["llm"]), MCP_LIST, at=("loaded",), stop=stop)
        assert seen == ["final answer"]

    def test_by_default_the_stop_is_the_debugger(self, monkeypatch):
        calls = []
        monkeypatch.setattr(builtins, "breakpoint", lambda *a, **k: calls.append("breakpoint"))
        scenario = SCENARIOS["full_path_with_mcp"]
        run_with_stops(scenario["message"], ScriptedLLM(**scenario["llm"]), MCP_LIST, at=("start",),
                       steps=["triage_specialist"])
        assert calls == ["breakpoint"]
