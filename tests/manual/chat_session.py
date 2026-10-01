"""
MANUAL script: a named chat with the whole agent and the REAL LLM, like a chat in an online LLM.
The name groups all its messages in Langfuse (Sessions); each message is its own trace inside it, and each step of a
message is a generation inside that trace. It costs money (cents) and needs the keys of .env.

    windows/Scripts/python.exe tests/manual/chat_session.py --name="Weather chat"            the weather example
    windows/Scripts/python.exe tests/manual/chat_session.py --name="My chat" "hi" "and now?"  your own messages

Writes tests/output/chat_session/<name>.md with the conversation, and for every message the time, the LLM calls, the
tokens and the cost (from config/*.json prices). Never prints keys. Not collected by pytest.
"""
import os
import re
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
from application.orchestration.support.model_selection import effective_models
from application.service.session_service import SessionService
from budget_run import Collector, usd
from infrastructure.outbound.llm.config import VercelAIConfig
from infrastructure.outbound.llm.vercel import VercelAIAdapter
from infrastructure.outbound.mcp.client_manager import MCPClientManager
from infrastructure.outbound.mcp.tool_executor import MCPToolExecutor
from infrastructure.outbound.usage.langfuse import LangfuseUsageReporter
from infrastructure.outbound.usage.prices import cost_usd, load_prices

OUT_DIR = os.path.join(PROJECT_ROOT, "tests", "output", "chat_session")

WEATHER = [
    "Hi! I would like to chat about the weather.",
    "What is the weather like in Madrid today?",
    "Should I take an umbrella with me tomorrow?",
    "OK. And what is the weather usually like in Valencia in October?",
]


def main():
    args = sys.argv[1:]
    name = next((a.split("=", 1)[1] for a in args if a.startswith("--name=")), "Weather chat")
    messages = [a for a in args if not a.startswith("--")] or WEATHER

    prices = load_prices()
    langfuse = LangfuseUsageReporter.from_env()
    collector = Collector(langfuse)
    executor = MCPToolExecutor(MCPClientManager([]))
    service = SessionService(outbound_port=VercelAIAdapter(Config=VercelAIConfig.from_env(tool_executor=executor)),
                             mcp_list=[], mcp_tools=executor, usage_reporter=collector)
    session_id = service.start_session(
        StartSessionRequestDTO(user_id="tester", username="tester", session_name=name)).session_id

    lines = [f"# Chat: {name}", "", "Models: " + ", ".join(f"{s}={m}" for s, (m, _) in effective_models().items()), ""]
    total = 0.0
    for text in messages:
        first = len(collector.calls)
        started = time.time()
        result = service.message_received(MessageReceivedRequestDTO(user_id="tester", session_id=session_id, message=text))
        seconds = time.time() - started
        calls = [r for _, r in collector.calls[first:]]

        per_step = OrderedDict()
        for r in calls:
            row = per_step.setdefault(r.phase_name, {"calls": 0, "tokens": 0, "cost": 0.0})
            row["calls"] += 1
            row["tokens"] += r.total_tokens
            row["cost"] += cost_usd(prices, r.model, r.prompt_tokens, r.completion_tokens, r.total_tokens) or 0.0
        cost = sum(r["cost"] for r in per_step.values())
        total += cost
        steps = ", ".join(f"{n} x{r['calls']}" if r["calls"] > 1 else n for n, r in per_step.items())

        lines += [f"**You:** {text}", "", f"**Agent:** {result.response if result.success else 'FAILED: ' + result.message}", "",
                  f"> {seconds:.1f} s, {len(calls)} LLM calls, {sum(r['tokens'] for r in per_step.values()):,} tokens, {usd(cost)}"
                  f" ({steps or 'no calls'})", ""]
        print(f"{seconds:5.1f}s {len(calls):>2} calls {usd(cost):>8}  {text[:50]}")

    lines += [f"**Chat total: {usd(total)}**"]
    if langfuse:
        langfuse.flush(30)
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, re.sub(r"[^A-Za-z0-9_-]+", "_", name) + ".md")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("chat total:", usd(total), "| file:", path)


if __name__ == "__main__":
    main()
