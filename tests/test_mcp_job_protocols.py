"""The two Dynamics job protocols (T-07.5, ADR-018): the shapes seen, read to the end by the engine of T-07.4.

The answers are the shapes of `dynamics_microservice` (the call of 2026-11-11 and the documents of T-01) with placeholder data.
"""

import json
import os
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from application.outbound.ports.mcp_ports import tool_wait_budget, watch_tool_failures
from infrastructure.outbound.mcp.config import load_mcp_configs, load_supported_mcp_configs
from infrastructure.outbound.mcp.job_follow_up import STILL_RUNNING_TEXT
from infrastructure.outbound.mcp.job_protocol import DONE, RUNNING, UNKNOWN, JobRef, get_protocol, job_protocol_problem, known_protocols
from infrastructure.outbound.mcp.tool_executor import MCPToolExecutor

PENDING_ONE = (
    "coverage: the order headers of one customer; steps: open_orders (pending); customer_no=CL-1001\n\n"
    "## open_orders (open)\n"
    "note: pending: the query is still running as job abc123 (running): read it with get_job_result"
)
PENDING_TWO = (
    "coverage: the order headers of one customer; steps: open_orders (pending), archived_orders (pending); customer_no=CL-1001\n\n"
    "## open_orders (open)\n"
    "note: pending: the query is still running as job j-open (running): read it with get_job_result\n\n"
    "## archived_orders (archived)\n"
    "note: pending: the query is still running as job j-arch (running): read it with get_job_result"
)
FINISHED = "returned: 2\ntotal: 2\njob_id: abc123\noffset: 0\n\nNo.|Status|Amount\nPV-1|Open|10\nPV-2|Open|20"
FINISHED_ARCHIVED = "returned: 1\ntotal: 1\njob_id: j-arch\noffset: 0\n\nNo.|Version\nPV-0|3"
STILL_RUNNING_READ = "status: running\njob_id: abc123\nnext_offset: 0"
V1_FIRST = "status: running\njob_id: j9\nnext_offset: 0"
READ_TOOL, CANCEL_TOOL = "get_job_result", "cancel_job"

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "mcp_job_answers")


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return f.read().rstrip("\n")


# ------------------------------------------------------------------ the fixture files (tests/fixtures/mcp_job_answers)


def test_each_protocol_reads_the_fixture_files_of_its_own_shape():
    pending, v1 = get_protocol("dynamics_pending"), get_protocol("dynamics_v1")

    assert pending.detect(fixture("dynamics_pending/first_one_table.txt")) == [JobRef("pend-1")]
    assert pending.detect(fixture("dynamics_pending/first_two_tables.txt")) == [JobRef("pend-open"), JobRef("pend-arch")]
    assert pending.state(fixture("dynamics_pending/read_done_open.txt")) == DONE
    assert pending.state(fixture("dynamics_pending/read_done_archived.txt")) == DONE
    assert pending.state(fixture("dynamics_pending/read_running.txt")) == RUNNING
    assert v1.detect(fixture("dynamics_v1/first_running.txt")) == [JobRef("job-1", 0)]
    assert v1.state(fixture("dynamics_v1/read_done.txt")) == DONE
    assert v1.state(fixture("dynamics_v1/read_running.txt")) == RUNNING


def test_a_protocol_finds_no_job_in_the_files_of_the_other_one():
    pending, v1 = get_protocol("dynamics_pending"), get_protocol("dynamics_v1")

    assert v1.detect(fixture("dynamics_pending/first_one_table.txt")) == []
    assert pending.detect(fixture("dynamics_v1/first_running.txt")) == []
    assert pending.detect(fixture("dynamics_v1/read_done.txt")) == [] and v1.detect(fixture("dynamics_pending/read_done_open.txt")) == []


def test_the_fixture_files_hold_no_real_data_only_placeholders():
    for protocol in ("dynamics_pending", "dynamics_v1"):
        for name in sorted(os.listdir(os.path.join(FIXTURES, protocol))):
            text = fixture(f"{protocol}/{name}")
            assert "@" not in text and "SUBARU" not in text.upper()            # no e-mail, no customer name of the real run


# ------------------------------------------------------------------ dynamics_pending


def test_a_pending_note_is_a_job_with_its_id():
    assert get_protocol("dynamics_pending").detect(PENDING_ONE) == [JobRef("abc123")]


def test_one_job_per_table_in_the_order_of_the_answer():
    assert get_protocol("dynamics_pending").detect(PENDING_TWO) == [JobRef("j-open"), JobRef("j-arch")]


@pytest.mark.parametrize("answer", ["", "returned: 2\ntotal: 2\n\nNo.|Status\nPV-1|Open",
                                    "## open_orders (open)\nNo.|Status\nPV-1|Open"])
def test_an_answer_with_no_pending_note_has_no_job(answer):
    assert get_protocol("dynamics_pending").detect(answer) == []


def test_a_pending_note_whose_id_cannot_be_read_is_still_a_job_so_that_it_fails_and_is_not_taken_as_a_result():
    answer = "## open_orders (open)\nnote: pending: the query is still running, ask later"

    assert get_protocol("dynamics_pending").detect(answer) == [JobRef("")]


def test_the_read_and_cancel_arguments_are_the_job_id_alone():
    protocol = get_protocol("dynamics_pending")

    assert protocol.read_arguments(JobRef("abc123", 7)) == {"job_id": "abc123"}
    assert protocol.cancel_arguments(JobRef("abc123")) == {"job_id": "abc123"}


@pytest.mark.parametrize("name", ["dynamics_pending", "dynamics_v1"])
@pytest.mark.parametrize("answer,state", [
    (FINISHED, DONE),
    ("returned: 0\ntotal: 0\njob_id: abc123\noffset: 0\n\nNo.|Status", DONE),
    (STILL_RUNNING_READ, RUNNING),
    ("the job is still queued: call again in a few seconds", RUNNING),
    ("coverage: x\nnote: pending: the job is running", RUNNING),
    ("something nobody planned for", UNKNOWN),
    ("", UNKNOWN),
    ("<html>502 Bad Gateway</html>", UNKNOWN),
])
def test_what_an_answer_read_from_a_job_says(name, answer, state):
    assert get_protocol(name).state(answer) == state


@pytest.mark.parametrize("name", ["dynamics_pending", "dynamics_v1"])
def test_a_customer_called_running_does_not_make_a_result_look_like_a_job_that_still_runs(name):
    assert get_protocol(name).state("returned: 1\ntotal: 1\n\nName|Status\nRunning Ltd|Open") == DONE


def test_merge_puts_the_result_in_place_of_the_note_and_keeps_the_rest():
    merged = get_protocol("dynamics_pending").merge(PENDING_ONE, [FINISHED])

    assert merged.startswith("coverage: the order headers of one customer; steps: open_orders (done); customer_no=CL-1001")
    assert "## open_orders (open)\nreturned: 2\ntotal: 2" in merged and merged.endswith("PV-2|Open|20")
    assert "pending" not in merged


def test_merge_keeps_two_tables_each_with_its_own_result_in_order():
    merged = get_protocol("dynamics_pending").merge(PENDING_TWO, [FINISHED, FINISHED_ARCHIVED])

    assert merged.index("## open_orders (open)") < merged.index("PV-1|Open|10") < merged.index("## archived_orders (archived)") < merged.index("PV-0|3")
    assert "steps: open_orders (done), archived_orders (done)" in merged and "pending" not in merged


# ------------------------------------------------------------------ dynamics_v1


def test_v1_a_running_status_is_a_job_with_its_id_and_its_offset():
    assert get_protocol("dynamics_v1").detect(V1_FIRST) == [JobRef("j9", 0)]
    assert get_protocol("dynamics_v1").detect("status: running\njob_id: j9\nnext_offset: 40") == [JobRef("j9", 40)]
    assert get_protocol("dynamics_v1").detect("status: running\njob_id: j9") == [JobRef("j9", None)]


@pytest.mark.parametrize("answer", ["", FINISHED, "status: ok\njob_id: x", PENDING_ONE])
def test_v1_anything_else_has_no_job(answer):
    assert get_protocol("dynamics_v1").detect(answer) == []


def test_v1_a_running_status_without_an_id_is_still_a_job_so_that_it_fails():
    assert get_protocol("dynamics_v1").detect("status: running\nnext_offset: 0") == [JobRef("", 0)]


def test_v1_the_offset_goes_as_offset_rows_only_when_there_is_one():
    protocol = get_protocol("dynamics_v1")

    assert protocol.read_arguments(JobRef("j9", 0)) == {"job_id": "j9", "offset_rows": 0}
    assert protocol.read_arguments(JobRef("j9")) == {"job_id": "j9"}
    assert protocol.cancel_arguments(JobRef("j9", 3)) == {"job_id": "j9"}


def test_v1_the_result_of_the_job_is_the_answer():
    assert get_protocol("dynamics_v1").merge(V1_FIRST, [FINISHED]) == FINISHED


# ------------------------------------------------------------------ the registry and the file


def test_both_protocols_are_registered():
    assert {"none", "dynamics_pending", "dynamics_v1"} <= set(known_protocols())


def test_the_dynamics_server_file_declares_a_protocol_its_tools_and_they_are_allowed():
    [server] = [s for s in load_mcp_configs() if s["name"] == "dynamics_microservice"]
    config = server["config"]

    assert config["job_protocol"] in ("dynamics_pending", "dynamics_v1")
    assert (config["job_read_tool"], config["job_cancel_tool"]) == (READ_TOOL, CANCEL_TOOL)
    assert job_protocol_problem(config) is None


def test_a_server_file_that_names_a_built_in_protocol_loads(tmp_path):
    for protocol in ("dynamics_pending", "dynamics_v1"):
        (tmp_path / f"{protocol}.json").write_text(json.dumps({protocol: {
            "type": "streamable_http", "url": "http://placeholder", "job_protocol": protocol, "job_read_tool": READ_TOOL,
            "allowed_tools": [READ_TOOL]}}), encoding="utf-8")

    assert sorted(s["name"] for s in load_supported_mcp_configs(str(tmp_path))) == ["dynamics_pending", "dynamics_v1"]


# ------------------------------------------------------------------ through the executor


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.now += seconds


class Manager:
    """The tools answer from a script by name (the last answer of a tool repeats); every call is recorded."""

    def __init__(self, protocol, answers):
        self.configs = {"local": {"name": "local", "type": "streamable_http", "config": {
            "url": "http://placeholder.invalid/mcp", "job_protocol": protocol, "job_read_tool": READ_TOOL, "job_cancel_tool": CANCEL_TOOL}}}
        self.answers, self.calls = answers, []

    @asynccontextmanager
    async def session_scope(self, server_name):
        async def call_tool(name, arguments=None):
            self.calls.append((name, arguments))
            queue = self.answers[name]
            item = queue.pop(0) if len(queue) > 1 else queue[0]
            return SimpleNamespace(isError=item.startswith("error"), content=[SimpleNamespace(text=item)])
        yield SimpleNamespace(call_tool=call_tool)


def execute(manager, budget=None):
    clock = Clock()
    executor = MCPToolExecutor(manager)
    executor._clock, executor._sleep = clock, clock.sleep
    executor.catalog._server_of_tool["customer_orders"] = "local"
    with watch_tool_failures() as failures:
        if budget is None:
            answer = executor.execute("customer_orders", {"customer_no": "CL-1001", "scope": "open"})
        else:
            with tool_wait_budget(budget):
                answer = executor.execute("customer_orders", {"customer_no": "CL-1001", "scope": "open"})
    return answer, failures.calls, clock


def test_a_pending_answer_is_read_to_its_result_the_way_the_real_call_of_2026_11_11_went():
    manager = Manager("dynamics_pending", {"customer_orders": [PENDING_ONE], READ_TOOL: [FINISHED]})

    answer, [record], _ = execute(manager)

    assert answer["is_error"] is False and "PV-2|Open|20" in answer["result"] and "pending" not in answer["result"]
    assert manager.calls[1:] == [(READ_TOOL, {"job_id": "abc123"})]
    assert (record.outcome, record.attempts) == ("job_done", 2)


def test_scope_all_with_two_jobs_gives_two_tables_when_both_end():
    manager = Manager("dynamics_pending", {"customer_orders": [PENDING_TWO],
                                           READ_TOOL: [STILL_RUNNING_READ, FINISHED, FINISHED_ARCHIVED]})

    answer, [record], _ = execute(manager)

    assert record.outcome == "job_done" and "PV-1|Open|10" in answer["result"] and "PV-0|3" in answer["result"]


def test_all_or_nothing_when_one_of_two_jobs_never_ends_no_table_is_given_and_it_is_cancelled():
    class Both(Manager):
        @asynccontextmanager
        async def session_scope(self, server_name):
            async def call_tool(name, arguments=None):
                self.calls.append((name, arguments))
                if name == "customer_orders":
                    text = PENDING_TWO
                elif name == READ_TOOL:
                    text = FINISHED if arguments["job_id"] == "j-open" else STILL_RUNNING_READ
                else:
                    text = "cancelled"
                return SimpleNamespace(isError=False, content=[SimpleNamespace(text=text)])
            yield SimpleNamespace(call_tool=call_tool)

    manager = Both("dynamics_pending", {})

    answer, [record], _ = execute(manager, budget=8)

    assert answer == {"result": STILL_RUNNING_TEXT, "is_error": False} and record.outcome == "job_cancelled"
    assert "PV-1" not in answer["result"]
    assert [c for c in manager.calls if c[0] == CANCEL_TOOL] == [(CANCEL_TOOL, {"job_id": "j-arch"})]


def test_a_pending_note_without_an_id_fails_and_is_final():
    manager = Manager("dynamics_pending", {"customer_orders": ["## t\nnote: pending: ask later"]})

    answer, [record], _ = execute(manager)

    assert answer["is_error"] is True and record.outcome == "job_unknown_shape"
    assert [name for name, _ in manager.calls] == ["customer_orders"]      # nothing was read: there was no id


def test_v1_a_running_answer_is_read_with_the_next_offset_as_offset_rows():
    manager = Manager("dynamics_v1", {"customer_orders": [V1_FIRST], READ_TOOL: [FINISHED]})

    answer, [record], _ = execute(manager)

    assert answer == {"result": FINISHED, "is_error": False} and record.outcome == "job_done"
    assert manager.calls[1] == (READ_TOOL, {"job_id": "j9", "offset_rows": 0})


def test_a_finished_answer_of_either_protocol_is_given_back_untouched():
    for protocol in ("dynamics_pending", "dynamics_v1"):
        manager = Manager(protocol, {"customer_orders": [FINISHED]})

        answer, [record], _ = execute(manager)

        assert answer == {"result": FINISHED, "is_error": False} and record.outcome == "ok"
        assert [name for name, _ in manager.calls] == ["customer_orders"]
