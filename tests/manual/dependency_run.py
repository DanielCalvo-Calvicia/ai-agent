"""
MANUAL script: simulates a plan whose actions depend on each other and on their subactions, and runs it through the
REAL executor, workers, draft and editor (real LLM calls: it costs money, cents with the budget profiles).

Only the planner (phase 2) is replaced: it "answers" a fixed plan of 5 actions with 5 subactions each (30 steps):

    1 Packing            1.1 .. 1.5            (1.2 needs 1.1, 1.4 needs 1.3)
    2 Logistics          2.1 .. 2.5            needs 1      (2.3 also needs 1.5)
    3 Paperwork          3.1 .. 3.5            needs nothing (3.4 needs 3.2 and 3.3)
    4 Cleaning           4.1 .. 4.5            needs 1 and 2
    5 Settling in        5.1 .. 5.5            needs 2, 3 and 4

A parent runs only after ALL its subactions and the actions it depends on are done. Triage and the safety gate are real.

    windows/Scripts/python.exe tests/manual/dependency_run.py                run it
    windows/Scripts/python.exe tests/manual/dependency_run.py --fail=3.2     the worker of step 3.2 gives no result:
                                                                             everything that needs it must be skipped

The report is tests/output/dependency_run/report.md (report_fail_<id>.md with --fail): the order the steps ran in, whether every dependency was respected,
which steps were skipped, and the cost. Every call also goes to Langfuse when it is configured. Never prints keys.
Not collected by pytest. The 30 worker calls run one after another: it can take several minutes.
"""
import os
import sys
import time
from collections import OrderedDict

from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tests"))
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(PROJECT_ROOT)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=False)

from application.inbound.dto.session import MessageReceivedRequestDTO, StartSessionRequestDTO
from application.outbound.ports.llm_ports import LLMOutboundPort
from application.service.session_service import SessionService
from budget_run import Collector, usd
from budget_table import budget_usd_per_message, load_budget
from infrastructure.outbound.llm.config import VercelAIConfig
from infrastructure.outbound.llm.response_mapper import build_response
from infrastructure.outbound.llm.vercel import VercelAIAdapter
from infrastructure.outbound.mcp.client_manager import MCPClientManager
from infrastructure.outbound.mcp.tool_executor import MCPToolExecutor
from infrastructure.outbound.usage.langfuse import LangfuseUsageReporter
from infrastructure.outbound.usage.prices import cost_usd, load_prices

OUT_DIR = os.path.join(PROJECT_ROOT, "tests", "output", "dependency_run")
MESSAGE = ("I am moving next month from my 2-bedroom flat in Madrid to a 3-bedroom flat in Valencia, with about 40 boxes, "
           "a sofa and a piano. There is no budget limit and no special requirement. You have all the information: "
           "do not ask me anything, plan the whole move for me now.")
PLANNER_FORMAT = "project_manager_phase2_response_format"
WORKER_FORMAT = "phase4_single_action_response_format"

# id -> (description, ids it needs, subaction ids listed in order)
STEPS = OrderedDict()


def step(step_id, description, needs=()):
    STEPS[step_id] = (description, list(needs))


def build_steps():
    packing = ["Make an inventory of every room", "Buy boxes and packing material", "Pack the rooms you use least",
               "Label every box with room and contents", "Pack an essentials bag for the first night"]
    logistics = ["Compare three moving companies", "Book the moving date", "Reserve parking for the truck",
                 "Plan the route and the order of loading", "Confirm the booking one week before"]
    paperwork = ["Give notice to the current landlord", "Change the address at the bank",
                 "Update the address at work and at the health service", "Transfer electricity, water and internet",
                 "Register at the town hall"]
    cleaning = ["Clean the kitchen and the appliances", "Clean the bathrooms", "Clean the floors and the windows",
                "Check the empty flat with the landlord", "Return the keys"]
    settling = ["Unpack the essentials bag", "Unpack the kitchen and the bedroom", "Check that utilities work",
                "Introduce yourself to the neighbours", "Do a first shopping trip nearby"]
    groups = [("1", "Packing", packing, [], {"1.2": ["1.1"], "1.4": ["1.3"]}),
              ("2", "Logistics", logistics, ["1"], {"2.3": ["1.5"]}),
              ("3", "Paperwork", paperwork, [], {"3.4": ["3.2", "3.3"]}),
              ("4", "Cleaning", cleaning, ["1", "2"], {}),
              ("5", "Settling in", settling, ["2", "3", "4"], {})]
    for number, title, subs, needs, sub_needs in groups:
        for index, text in enumerate(subs, 1):
            step(f"{number}.{index}", f"{title}: {text}", sub_needs.get(f"{number}.{index}", []))
        step(number, f"{title}: complete this part of the move", needs)


def children(parent_id):
    return [i for i in STEPS if i.startswith(parent_id + ".")]


def plan_json():
    def action(step_id):
        description, needs = STEPS[step_id]
        item = {"id": step_id, "description": description, "action_type": "generation", "dependencies": needs,
                "required_inputs": [], "output": "", "error": "",
                "mcp_context": {"server_id": "", "tool_name": "", "parameters": {}}}
        if "." not in step_id:
            item["subactions"] = [action(child) for child in children(step_id)]
        return item

    return {"actions": [action(i) for i in STEPS if "." not in i],
            "next_step": {"ready_to_execute": True, "status": "proceed", "recommended_action": "",
                          "blocking_reason": "", "requested_user_input": []}}


class ScriptedPlanner(LLMOutboundPort):
    """The real adapter for everything except the planner (and, with --fail, one worker)."""

    def __init__(self, inner, failing_id=None):
        self.inner = inner
        self.failing_description = STEPS[failing_id][0] if failing_id else None
        self.failing_id = failing_id
        self.failing_marker = f"'action': Action(id=Id(value='{failing_id}')" if failing_id else None

    def ask(self, payload):
        name = payload.response_format.name if payload.response_format else ""
        if name == PLANNER_FORMAT:
            return build_response(plan_json(), {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        if name == WORKER_FORMAT and self.failing_marker and self.failing_marker in payload.message.content:
            empty = {"actions": [{"id": self.failing_id, "description": self.failing_description, "action_type": "generation",
                                  "dependencies": [], "required_inputs": [], "output": "", "error": "",
                                  "mcp_context": {"server_id": "", "tool_name": "", "parameters": {}}}]}
            return build_response(empty, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        return self.inner.ask(payload)


def all_inputs(step_id):
    """What a step waits for: its subactions and the ids it depends on."""
    return children(step_id) + STEPS[step_id][1]


def main():
    build_steps()
    failing = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--fail=")), None)
    if failing and failing not in STEPS:
        sys.exit(f"unknown step {failing!r}. Steps: {', '.join(STEPS)}")

    prices, budget = load_prices(), load_budget()
    collector = Collector(LangfuseUsageReporter.from_env())
    executor = MCPToolExecutor(MCPClientManager([]))
    llm = ScriptedPlanner(VercelAIAdapter(Config=VercelAIConfig.from_env(tool_executor=executor)), failing)
    service = SessionService(outbound_port=llm, mcp_list=[], mcp_tools=executor, usage_reporter=collector)
    session_id = service.start_session(StartSessionRequestDTO(user_id="tester", username="tester")).session_id

    started = time.time()
    result = service.message_received(MessageReceivedRequestDTO(user_id="tester", session_id=session_id, message=MESSAGE))
    seconds = time.time() - started
    calls = [r for _, r in collector.calls]

    ran = [r.action_id for r in calls if r.phase_name == "cognitive_worker"]
    position = {step_id: n for n, step_id in enumerate(ran, 1)}
    skipped = [i for i in STEPS if i not in position]

    # Which steps must be skipped because something they need did not produce a result.
    dead = set([failing] if failing else [])
    changed = True
    while changed:
        changed = False
        for i in STEPS:
            if i not in dead and any(need in dead for need in all_inputs(i)):
                dead.add(i)
                changed = True

    rows, violations = [], []
    for i, (description, needs) in STEPS.items():
        inputs = all_inputs(i)
        if i in position:
            late = [need for need in inputs if need not in position or position[need] > position[i]]
            if late:
                violations.append((i, late))
        state = f"ran, #{position[i]}" if i in position else "skipped"
        rows.append(f"| {i} | {description[:58]} | {', '.join(children(i)) or '-'} | {', '.join(needs) or '-'} | {state} |")

    per_step = OrderedDict()
    for r in calls:
        row = per_step.setdefault(r.phase_name, {"calls": 0, "sent": 0, "answered": 0, "cost": 0.0})
        row["calls"] += 1
        row["sent"] += r.prompt_tokens
        row["answered"] += r.completion_tokens
        row["cost"] += cost_usd(prices, r.model, r.prompt_tokens, r.completion_tokens, r.total_tokens) or 0.0
    total = sum(r["cost"] for r in per_step.values())

    expected_skipped = sorted(dead - ({failing} if failing else set()), key=list(STEPS).index)
    lines = ["# Dependency run", "", f"Message: {MESSAGE}", "",
             f"Failing worker: {failing}" if failing else "No failures injected.", "",
             f"success={result.success}, {seconds:.0f}s, {len(calls)} LLM calls (the planner is scripted, so it is not one of them), "
             f"{len(ran)} worker calls.", "",
             "## Was every dependency respected?", "",
             "**Nothing ran: the run stopped before the plan (triage or the gate asked the user something). Nothing was checked.**"
             if not ran else
             "**Yes: no step ran before something it needs.**" if not violations else
             "**NO:** " + "; ".join(f"{i} ran before {', '.join(late)}" for i, late in violations), "",
             ("Skipped steps: " + (", ".join(skipped) or "none") + ". Expected to be skipped: "
              + (", ".join(expected_skipped) or "none") + ". "
              + ("They match." if sorted(skipped, key=list(STEPS).index) == sorted(dead - {failing}, key=list(STEPS).index) or not failing
                 else "They DIFFER.")) if failing else "Nothing should be skipped.",
             "", "## Every step", "",
             "| Step | What | Subactions it waits for | Actions it depends on | Result |", "|---|---|---|---|---|", *rows,
             "", "## Order the workers ran in", "", ", ".join(ran) or "none", "", "## Cost", "",
             "| Step | Calls | Sent | Answered | Cost |", "|---|---|---|---|---|"]
    lines += [f"| {n} | {r['calls']} | {r['sent']:,} | {r['answered']:,} | {usd(r['cost'])} |" for n, r in per_step.items()]
    lines += [f"| **Total** | {len(calls)} | | | **{usd(total)}** = {total * 1000 / budget['usd_per_eur']:.2f} EUR per 1,000 such messages "
              f"(limit {budget['eur_per_month']} EUR = {usd(budget_usd_per_message(budget))} per message) |", "",
              f"Reply: {result.response!r}" if result.success else f"FAILED: {result.message}"]

    if collector.langfuse:
        collector.langfuse.flush(30)
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"report_fail_{failing}.md" if failing else "report.md")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{'ok' if result.success else 'FAILED'}  {seconds:.0f}s  {len(ran)} worker calls  skipped={skipped}  "
          f"violations={violations}  cost={usd(total)}")
    print("report:", path)


if __name__ == "__main__":
    main()
