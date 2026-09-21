"""
MANUAL script: sends real messages through the WHOLE agent with the profile now active in config/step_models.json
(real LLM calls: it costs money, cents with the budget profiles) and reports what every step cost.

    windows/Scripts/python.exe tests/manual/budget_run.py                  the two default messages
    windows/Scripts/python.exe tests/manual/budget_run.py "your message"   your own messages

A fake local MCP pantry server (tool count_stock) is started so the tool steps (5 and 6) run too. Every call also goes to Langfuse when
LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set. The report is written to tests/output/budget_run/report.md
(cost of each step, tokens with thinking, and the projection for 1,000 messages against config/budget.json).
Never prints keys. Not collected by pytest.
"""
import os
import socket
import sys
import threading
import time
from collections import OrderedDict

import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tests"))
os.chdir(PROJECT_ROOT)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=False)

from application.inbound.dto.session import MessageReceivedRequestDTO, StartSessionRequestDTO
from application.orchestration.model_selection import effective_models
from application.outbound.ports.usage_ports import UsageReporterPort
from application.service.session_service import SessionService
from budget_table import budget_usd_per_message, load_budget
from infrastructure.outbound.llm.config import VercelAIConfig
from infrastructure.outbound.llm.vercel import VercelAIAdapter
from infrastructure.outbound.mcp.client_manager import MCPClientManager
from infrastructure.outbound.mcp.tool_executor import MCPToolExecutor
from infrastructure.outbound.usage.langfuse import LangfuseUsageReporter
from infrastructure.outbound.usage.prices import billed_output_tokens, cost_usd, load_prices

OUT_DIR = os.path.join(PROJECT_ROOT, "tests", "output", "budget_run")

MESSAGES = [
    "Plan a birthday party for 10 people this Saturday: list what to buy, a schedule for the day, "
    "a message to invite the guests, and check with the pantry tool how many plates and cups I already have at home.",
    "Hello, how are you?",
]


class Collector(UsageReporterPort):
    """Keeps every call of the run next to the trace it belongs to, and forwards it to Langfuse if there is one."""

    def __init__(self, langfuse):
        self.langfuse = langfuse
        self.calls = []

    def report(self, record, trace_id, session_id, details=None):
        self.calls.append((trace_id, record))
        if self.langfuse:
            self.langfuse.report(record, trace_id, session_id, details)


def start_fake_mail_server() -> str:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    mcp = FastMCP("fake-pantry")

    @mcp.tool()
    def count_stock(item: str) -> str:
        """Counts how many units of an item the user already has at home (plates, cups, candles, drinks...)."""
        return f"You have 6 units of {item} at home."

    server = uvicorn.Server(uvicorn.Config(mcp.sse_app(), host="127.0.0.1", port=port, log_config=None))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    return f"http://127.0.0.1:{port}/sse"


def usd(value):
    return "$0" if not value else f"${value:.4f}"


def main():
    prices = load_prices()
    budget = load_budget()
    langfuse = LangfuseUsageReporter.from_env()
    delivery = []
    if langfuse:
        original = langfuse.send

        def checked(events):
            try:
                original(events)
                delivery.append("ok")
            except Exception as error:
                delivery.append(f"{type(error).__name__}: {str(error)[:120]}")
                raise

        langfuse.send = checked
    collector = Collector(langfuse)

    url = start_fake_mail_server()
    mcp_list = [{"name": "pantry", "type": "sse", "config": {"type": "sse", "url": url}}]
    executor = MCPToolExecutor(MCPClientManager(mcp_list))
    service = SessionService(outbound_port=VercelAIAdapter(Config=VercelAIConfig.from_env(tool_executor=executor)),
                             mcp_list=mcp_list, mcp_tools=executor, usage_reporter=collector)
    session_id = service.start_session(StartSessionRequestDTO(user_id="tester", username="tester")).session_id

    lines = ["# Budget run", "", f"Profile in use: {os.environ.get('AI_AGENT_MODELS_FILE') or 'config/step_models.json'}", "",
             "| Step | Model |", "|---|---|"]
    lines += [f"| {step} | `{model}` ({source}) |" for step, (model, source) in effective_models().items()]

    for text in (sys.argv[1:] or MESSAGES):
        first = len(collector.calls)
        started = time.time()
        result = service.message_received(MessageReceivedRequestDTO(user_id="tester", session_id=session_id, message=text))
        seconds = time.time() - started
        calls = [r for _, r in collector.calls[first:]]

        per_step = OrderedDict()
        for r in calls:
            row = per_step.setdefault(r.phase_name, {"model": r.model, "calls": 0, "sent": 0, "answered": 0, "thinking": 0, "cost": 0.0})
            row["calls"] += 1
            row["sent"] += r.prompt_tokens
            row["answered"] += r.completion_tokens
            row["thinking"] += max(0, r.total_tokens - r.prompt_tokens - r.completion_tokens)
            row["cost"] += cost_usd(prices, r.model, r.prompt_tokens, r.completion_tokens, r.total_tokens) or 0.0
        total = sum(row["cost"] for row in per_step.values())

        lines += ["", f"## Message: {text[:90]}", "",
                  f"success={result.success}, {seconds:.1f}s, {len(calls)} LLM calls.", "",
                  "| Step | Model | Calls | Sent | Answered | Thinking | Cost |", "|---|---|---|---|---|---|---|"]
        lines += [f"| {name} | `{r['model']}` | {r['calls']} | {r['sent']:,} | {r['answered']:,} | {r['thinking']:,} | {usd(r['cost'])} |"
                  for name, r in per_step.items()]
        lines += [f"| **Total** | | {len(calls)} | {sum(r['sent'] for r in per_step.values()):,} | "
                  f"{sum(r['answered'] for r in per_step.values()):,} | {sum(r['thinking'] for r in per_step.values()):,} | **{usd(total)}** |",
                  "", f"Projection: {usd(total)} x 1,000 messages = **{total * 1000 / budget['usd_per_eur']:.2f} EUR** "
                      f"(limit {budget['eur_per_month']} EUR = {usd(budget_usd_per_message(budget))} per message).",
                  "", f"Reply: {result.response!r}" if result.success else f"FAILED: {result.message}"]
        print(f"{'ok' if result.success else 'FAILED'}  {seconds:5.1f}s  {len(calls):>3} calls  {usd(total)}  <- {text[:60]}")

    if langfuse:
        langfuse.flush(20)
        lines += ["", f"Langfuse: {len(delivery)} report batches sent, results: {sorted(set(delivery)) or 'none'}."]
        print("langfuse:", sorted(set(delivery)) or "nothing sent")
    else:
        lines += ["", "Langfuse: not configured (LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY empty)."]
        print("langfuse: not configured")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "report.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("report:", os.path.join(OUT_DIR, "report.md"))


if __name__ == "__main__":
    main()
