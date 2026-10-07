"""
The four flows of the service (identification, conversation, special, movement), the generic pipeline hooks, and the
one set of routes. No real LLM, network or MCP server is used.
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
from application.orchestration.flows.conversation import CONVERSATION_FLOW
from application.orchestration.flows.identification import IDENTIFICATION_FLOW
from application.orchestration.flows.movement import MOVEMENT_FLOW
from application.orchestration.flows.registry import FLOWS, FlowRegistry
from application.orchestration.flows.special import SPECIAL_FLOW
from application.orchestration.support.metrics import SessionMetrics
from application.orchestration.engine.pipeline import Pipeline
from application.orchestration.phases.phase import Step
from application.service.session_service import SessionService
from infrastructure.inbound.http.fastapi import SessionFastAPI

from test_flow_golden import ScriptedLLM


@pytest.fixture(autouse=True)
def _project_cwd(monkeypatch):
    monkeypatch.chdir(PROJECT_ROOT)


def _app() -> TestClient:
    app = FastAPI()
    SessionFastAPI(App=app, SessionPort=SessionService(outbound_port=ScriptedLLM(), mcp_list=[]))
    return TestClient(app)


class TestRegistry:
    def test_the_flows_are_registered_under_their_public_names(self):
        assert FLOWS.get("identification") is IDENTIFICATION_FLOW
        assert FLOWS.get("conversation") is CONVERSATION_FLOW
        assert FLOWS.get("special") is SPECIAL_FLOW
        assert FLOWS.get("movement") is MOVEMENT_FLOW
        assert FLOWS.names() == ["identification", "conversation", "special", "movement"]

    def test_an_unknown_flow_fails_loudly(self):
        with pytest.raises(KeyError, match="unknown flow"):
            FLOWS.get("nope")

    def test_a_flow_cannot_be_registered_twice(self):
        with pytest.raises(ValueError, match="already registered"):
            FlowRegistry([CONVERSATION_FLOW, CONVERSATION_FLOW])

    def test_the_registry_is_iterable_in_registration_order(self):
        assert [flow.name for flow in FlowRegistry([CONVERSATION_FLOW])] == ["conversation"]


class TestTheStepsOfEachFlow:
    @pytest.mark.parametrize("flow,steps", [
        (IDENTIFICATION_FLOW, ["triage_specialist"]),
        (CONVERSATION_FLOW, ["draft_writer", "editor_in_chief"]),
        (SPECIAL_FLOW, ["project_manager", "safety_quality_gatekeeper", "action_executor", "draft_writer", "editor_in_chief"]),
        (MOVEMENT_FLOW, ["motion_planner", "motion_validator"]),
    ])
    def test_the_steps(self, flow, steps):
        assert [step.name for step in Pipeline(ScriptedLLM(), [], SessionMetrics(), flow=flow).steps] == steps

    def test_only_identification_runs_triage(self):
        for flow in (CONVERSATION_FLOW, SPECIAL_FLOW, MOVEMENT_FLOW):
            assert "triage_specialist" not in [s.name for s in Pipeline(ScriptedLLM(), [], SessionMetrics(), flow=flow).steps]

    def test_a_pipeline_tags_its_result_with_the_flow_and_the_state(self):
        result = Pipeline(ScriptedLLM(), [], SessionMetrics(), flow=IDENTIFICATION_FLOW).run("hello")
        assert result.state is not None
        assert result.flow == "identification" and result.state.task_category is not None


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
            Pipeline(ScriptedLLM(), [], SessionMetrics())  # pyright: ignore[reportCallIssue]


class TestRoutes:
    def test_a_session_works_on_the_session_routes(self):
        client = _app()
        started = client.post("/session/start", json={"user_id": "tester", "username": "t"})
        assert started.status_code == 200
        session_id = started.json()["data"]["session_id"]

        reply = client.post("/session/message",
                            json={"user_id": "tester", "session_id": session_id, "message": "hello"})
        assert reply.json()["data"]["success"] is True
        assert reply.json()["data"]["response"]
        assert reply.json()["data"]["flow"] == "special"           # the scripted triage says domain "system"

        ended = client.post("/session/end", json={"user_id": "tester", "session_id": session_id})
        assert ended.json()["data"]["success"] is True

    def test_there_are_no_routes_per_flow_any_more(self):
        client = _app()
        assert client.post("/conversation-flow/session/start", json={"user_id": "tester", "username": "t"}).status_code == 404
        assert client.post("/motion-flow/session/start", json={"user_id": "tester", "username": "t"}).status_code == 404

    def test_health_is_served_at_the_top(self):
        client = _app()
        assert client.get("/health").json()["data"]["healthy"] is True
        assert client.get("/available").json()["data"]["is_available"] is True

    def test_the_session_routes_are_not_deprecated(self):
        paths = _app().get("/openapi.json").json()["paths"]
        assert not paths["/session/message"]["post"].get("deprecated")

    def test_an_unknown_session_asks_the_caller_to_start_a_new_one(self):
        client = _app()
        body = client.post("/session/message",
                           json={"user_id": "tester", "session_id": "nope", "message": "hello"}).json()
        assert body["data"]["error_code"] == "SESSION_NOT_FOUND"
