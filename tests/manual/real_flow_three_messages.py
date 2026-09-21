"""
MANUAL script: a conversation with the whole agent and the REAL LLM. With no arguments it sends the
example messages of the owner (small talk, the date, a question that needs an answer, something the robot
cannot do...) in ONE session; otherwise each argument is a message. Models come from the defaults or
AI_AGENT_MODEL_PHASE_<n>. Set WITH_FAKE_MAIL=1 to also offer a fake local MCP mail server.
It costs money and needs the keys of .env. Run it with the venv python from anywhere:
    windows/Scripts/python.exe tests/manual/real_flow_three_messages.py

The MCP server is a small fake one started on a free local port (tool: count_emails, always answers 42),
so the MCP path can be tried without the real aws_microservice. Not collected by pytest.

Prints, for every LLM call: phase, model, seconds, tokens and any error. Never prints keys.
"""
import os
import socket
import sys
import threading
import time

import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=False)

from application.inbound.dto.session import MessageReceivedRequestDTO, StartSessionRequestDTO
from application.outbound.ports.llm_ports import LLMOutboundPort
from application.service.session_service import SessionService
from infrastructure.outbound.llm.config import VercelAIConfig
from infrastructure.outbound.llm.vercel import VercelAIAdapter
from infrastructure.outbound.mcp.client_manager import MCPClientManager
from infrastructure.outbound.mcp.tool_executor import MCPToolExecutor

MESSAGES = [
    "Hello, how are you?",                                        # small talk
    "Which day is today?",                                        # needs the current date
    "My family has 4 people. Make a table with each name.",       # must ask for the names
    "What is the weather like?",                                  # does not answer: it must ask again
    "Ana, Luis, Pepe and Mia",                                    # the answer: it must continue
    "Can you delete this file?",                                  # no file service
    "Can you jump?",                                              # the robot cannot
    "How many emails do I have?",                                 # no email service
]


def start_fake_mail_server() -> str:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    mcp = FastMCP("fake-mail")

    @mcp.tool()
    def count_emails(folder: str = "inbox") -> str:
        """Counts the emails of a mail folder."""
        return f"You have 42 emails in {folder}."

    server = uvicorn.Server(uvicorn.Config(mcp.sse_app(), host="127.0.0.1", port=port, log_config=None))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    return f"http://127.0.0.1:{port}/sse"


class Recorder(LLMOutboundPort):
    """Wraps the real adapter and prints one line per call."""

    def __init__(self, inner: LLMOutboundPort):
        self.inner = inner
        self.calls = []

    def ask(self, Payload):
        name = Payload.response_format.name if Payload.response_format else "text"
        started = time.time()
        try:
            response = self.inner.ask(Payload)
        except Exception as e:
            seconds = time.time() - started
            print(f"    {name:<52} {Payload.model.id:<13} {seconds:5.1f}s  ERROR {type(e).__name__}: {str(e)[:300]}")
            self.calls.append((name, seconds, 0, str(e)))
            raise
        seconds = time.time() - started
        tokens = response.tokens_usage.total_tokens if response.tokens_usage else 0
        print(f"    {name:<52} {Payload.model.id:<13} {seconds:5.1f}s  {tokens:>6} tokens")
        self.calls.append((name, seconds, tokens, ""))
        self._show(response)
        return response

    @staticmethod
    def _show(response):
        """The parts of the answer that steer the flow."""
        step = response.next_step
        if step:
            questions = step.requested_user_input.get_value() if step.requested_user_input else []
            reason = step.blocking_reason.get_value() if step.blocking_reason else ""
            print(f"        next_step: {step.status.get_value()} | reason: {reason!r} | ask: {questions}")
        if response.actions:
            for a in response.actions:
                print(f"        action {a.id.get_value()} [{a.action_type.get_value() if a.action_type else None}] "
                      f"deps={a.dependencies.get_value() if a.dependencies else []} "
                      f"subs={list(a.subactions) if a.subactions else []} "
                      f"out={a.output.get_value()[:60] if a.output else None!r} err={a.error.get_value() if a.error else None!r}")
        if response.task_category:
            print(f"        complexity: {response.task_category.complexity.get_value()}")


def main():
    mcp_list = []
    if os.environ.get("WITH_FAKE_MAIL") == "1":
        url = start_fake_mail_server()
        mcp_list = [{"name": "mail", "type": "sse", "config": {"type": "sse", "url": url}}]
    executor = MCPToolExecutor(MCPClientManager(mcp_list))

    recorder = Recorder(VercelAIAdapter(Config=VercelAIConfig.from_env(tool_executor=executor)))
    service = SessionService(outbound_port=recorder, mcp_list=mcp_list, mcp_tools=executor)
    session_id = service.start_session(StartSessionRequestDTO(user_id="tester", username="tester")).session_id

    for text in (sys.argv[1:] or MESSAGES):
        print(f"\nUSER: {text}")
        first_call = len(recorder.calls)
        started = time.time()
        result = service.message_received(
            MessageReceivedRequestDTO(user_id="tester", session_id=session_id, message=text))
        seconds = time.time() - started
        calls = recorder.calls[first_call:]
        print(f"  -> success={result.success}  {seconds:.1f}s  {len(calls)} calls  {sum(c[2] for c in calls)} tokens")
        print(f"  REPLY: {result.response!r}")
        if not result.success:
            print(f"  FAILED: {result.message}")


if __name__ == "__main__":
    main()
