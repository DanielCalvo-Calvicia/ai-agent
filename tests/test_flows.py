"""
Several flows in one service: the registry, the generic pipeline hooks, and one set of routes per flow.
No real LLM, network or MCP server is used.
"""
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from application.orchestration.engine.flow import Flow
from application.orchestration.flows.registry import FLOWS, FlowRegistry
from application.orchestration.flows.conversation_flow import CONVERSATION_FLOW
from application.orchestration.support.metrics import SessionMetrics
from application.orchestration.engine.pipeline import Pipeline
from application.orchestration.phases.phase import Step
from application.service.session_service import SessionService
from infrastructure.inbound.http.fastapi import SessionFastAPI, message_data_for

from test_flow_golden import ScriptedLLM


@pytest.fixture(autouse=True)
def _project_cwd(monkeypatch):
    monkeypatch.chdir(PROJECT_ROOT)


def _app(flows=None) -> TestClient:
    """One service and one set of routes per flow, like the composition root, plus the legacy alias."""
    app = FastAPI()
    services = {}
    for flow in (flows or list(FLOWS)):
        services[flow.name] = SessionService(outbound_port=ScriptedLLM(), mcp_list=[], flow=flow)
        SessionFastAPI(App=app, SessionPort=services[flow.name], prefix=f"/{flow.name}", tag=flow.name,
                       include_health=False, message_to_data=message_data_for(flow.name))
    SessionFastAPI(App=app, SessionPort=services[CONVERSATION_FLOW.name], deprecated=True)
    return TestClient(app)


class TestRegistry:
    def test_the_flows_are_registered_under_their_public_names(self):
        assert FLOWS.get("conversation-flow") is CONVERSATION_FLOW
        assert FLOWS.names() == ["conversation-flow", "motion-flow"]

    def test_an_unknown_flow_fails_loudly(self):
        with pytest.raises(KeyError, match="unknown flow"):
            FLOWS.get("nope")

    def test_a_flow_cannot_be_registered_twice(self):
        with pytest.raises(ValueError, match="already registered"):
            FlowRegistry([CONVERSATION_FLOW, CONVERSATION_FLOW])

    def test_the_registry_is_iterable_in_registration_order(self):
        assert [flow.name for flow in FlowRegistry([CONVERSATION_FLOW])] == ["conversation-flow"]


class TestGenericPipeline:
    def test_a_flow_with_its_own_steps_runs_only_those_steps(self):
        ran = []
        flow = Flow(
            name="tiny-flow",
            build_steps=lambda context: [Step("one", lambda state: ran.append("one")),
                                         Step("two", lambda state: ran.append("two"))],
        )
        result = Pipeline(ScriptedLLM(), [], SessionMetrics(), flow=flow).run("hi")
        assert ran == ["one", "two"]
        assert result.paused is None

    def test_jump_after_skips_steps(self):
        ran = []
        flow = Flow(
            name="jumping-flow",
            build_steps=lambda context: [Step(name, lambda state, n=name: ran.append(n)) for name in ("a", "b", "c")],
            jump_after=lambda step, state: "c" if step.name == "a" else None,
        )
        Pipeline(ScriptedLLM(), [], SessionMetrics(), flow=flow).run("hi")
        assert ran == ["a", "c"]

    def test_the_flow_builds_its_own_result(self):
        from application.orchestration.state.paused_run import FlowResult
        flow = Flow(
            name="result-flow",
            build_steps=lambda context: [],
            build_result=lambda state: FlowResult(reply="built by the flow"),
        )
        assert Pipeline(ScriptedLLM(), [], SessionMetrics(), flow=flow).run("hi").reply == "built by the flow"

    def test_a_pipeline_is_always_given_its_flow(self):
        # the engine knows no particular agent, so it has no default one
        with pytest.raises(TypeError):
            Pipeline(ScriptedLLM(), [], SessionMetrics())


class TestRoutes:
    @pytest.mark.parametrize("prefix", ["/conversation-flow", ""])
    def test_a_session_works_on_the_flow_routes_and_on_the_legacy_alias(self, prefix):
        client = _app()
        started = client.post(f"{prefix}/session/start", json={"user_id": "tester", "username": "t"})
        assert started.status_code == 200
        session_id = started.json()["data"]["session_id"]

        reply = client.post(f"{prefix}/session/message",
                            json={"user_id": "tester", "session_id": session_id, "message": "hello"})
        assert reply.json()["data"]["success"] is True
        assert reply.json()["data"]["response"]

        ended = client.post(f"{prefix}/session/end", json={"user_id": "tester", "session_id": session_id})
        assert ended.json()["data"]["success"] is True

    def test_the_legacy_alias_and_the_flow_routes_share_the_sessions(self):
        client = _app()
        session_id = client.post("/session/start", json={"user_id": "tester", "username": "t"}).json()["data"]["session_id"]
        reply = client.post("/conversation-flow/session/message",
                            json={"user_id": "tester", "session_id": session_id, "message": "hello"})
        assert reply.json()["data"]["success"] is True

    def test_health_is_served_once_at_the_top(self):
        client = _app()
        assert client.get("/health").json()["data"]["healthy"] is True
        assert client.get("/conversation-flow/health").status_code == 404

    def test_the_alias_is_marked_deprecated_in_the_openapi(self):
        paths = _app().get("/openapi.json").json()["paths"]
        assert paths["/session/message"]["post"].get("deprecated") is True
        assert not paths["/conversation-flow/session/message"]["post"].get("deprecated")

    def test_each_flow_has_its_own_sessions(self):
        other = Flow(name="other-flow", build_steps=lambda context: [])
        client = _app([CONVERSATION_FLOW, other])
        session_id = client.post("/conversation-flow/session/start",
                                 json={"user_id": "tester", "username": "t"}).json()["data"]["session_id"]

        unknown_there = client.post("/other-flow/session/message",
                                    json={"user_id": "tester", "session_id": session_id, "message": "hello"})
        assert unknown_there.json()["data"]["error_code"] == "SESSION_NOT_FOUND"
