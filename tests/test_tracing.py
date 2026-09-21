import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient
from shared_logging.testing import capture

TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
TRACEPARENT = f"00-{TRACE_ID}-b7ad6b7169203331-01"


def test_app_continues_the_incoming_trace_and_logs_the_service_name():
    from composition_root.main import app

    with capture("ai-agent") as logs:
        response = TestClient(app).get("/openapi.json", headers={"traceparent": TRACEPARENT})

    assert response.status_code == 200
    assert response.headers["x-trace-id"] == TRACE_ID
    request_logs = [r for r in logs.records if r["logger"] == "shared_logging.http"]
    assert request_logs and {r["trace_id"] for r in request_logs} == {TRACE_ID}


def test_mcp_connections_forward_the_trace_context(monkeypatch):
    import asyncio

    from infrastructure.outbound.mcp import client_manager
    from shared_logging import continue_trace

    captured = {}

    class FakeSse:
        def __init__(self, url, headers=None):
            captured["headers"] = headers

        async def __aenter__(self):
            raise RuntimeError("stop after headers were captured")

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(client_manager, "sse_client", FakeSse)
    manager = client_manager.MCPClientManager(
        [{"name": "aws", "type": "sse", "config": {"url": "http://x/mcp/sse"}}]
    )

    async def run():
        with capture("ai-agent"), continue_trace({"traceparent": TRACEPARENT}, "POST /session/message"):
            try:
                async with manager.session_scope("aws"):
                    pass
            except RuntimeError:
                pass

    asyncio.run(run())
    assert captured["headers"]["traceparent"].split("-")[1] == TRACE_ID
