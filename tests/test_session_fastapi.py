import os
import sys
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.outbound.ports.llm_ports import LLMOutboundPort
from application.service.session_service import SessionService
from infrastructure.inbound.http.fastapi import SessionFastAPI
from domain.entities.payload import Payload
from domain.entities.response import Response


# ===============================================
#  MOCK LLM ADAPTER
# ===============================================

class MockLLMAdapter(LLMOutboundPort):
    """
    Fake LLM adapter that returns a deterministic response.
    Allows E2E tests to run without real API keys.
    """

    def __init__(self):
        self._started = True

    def ask(self, Payload: Payload) -> Response:
        return Response(
                intent=None,
                user_goal=None,
                mcp_routing=None,
                task_category=None,
                actions=None,
                text="Mock LLM response"
            )

    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        self._started = False

    def is_active(self) -> bool:
        return self._started


# ===============================================
#  TEST FIXTURES
# ===============================================

@pytest.fixture
def test_app():
    """
    Builds the full dependency chain with the mock adapter
    and returns a TestClient ready to hit the endpoints.
    """
    mockAdapter = MockLLMAdapter()
    sessionService = SessionService(outbound_port=mockAdapter)

    app = FastAPI()
    SessionFastAPI(App=app, SessionPort=sessionService)

    return TestClient(app)


@pytest.fixture
def started_session(test_app):
    """
    Convenience fixture: starts a session and returns (client, session_id).
    """
    payload = {
        "user_id": "test-user-001",
        "username": "TestUser",
        "email": "test@example.com",
    }
    response = test_app.post("/session/start", json=payload)
    data = response.json()
    sessionId = data["data"]["session_id"]
    return test_app, sessionId


# ===============================================
#  TESTS: /session/start
# ===============================================

class TestStartSession:
    def test_start_session_success(self, test_app):
        payload = {
            "user_id": "test-user-001",
            "username": "TestUser",
            "email": "test@example.com",
        }

        response = test_app.post("/session/start", json=payload)
        data = response.json()

        assert response.status_code == 200
        assert data["status"] == "success"
        assert data["action"] == "start_session"
        assert data["status_code"] == 200
        assert data["data"]["session_id"] != ""
        assert data["data"]["success"] is True

    def test_start_session_without_email(self, test_app):
        payload = {
            "user_id": "test-user-002",
            "username": "NoEmailUser",
        }

        response = test_app.post("/session/start", json=payload)
        data = response.json()

        assert response.status_code == 200
        assert data["status"] == "success"
        assert data["data"]["session_id"] != ""

    def test_start_session_missing_username(self, test_app):
        payload = {
            "user_id": "test-user-003",
        }

        response = test_app.post("/session/start", json=payload)

        # FastAPI returns 422 for missing required fields
        assert response.status_code == 422

    def test_start_session_missing_user_id(self, test_app):
        payload = {
            "username": "NoIdUser",
        }

        response = test_app.post("/session/start", json=payload)

        assert response.status_code == 422

    def test_start_session_user_id_too_short(self, test_app):
        payload = {
            "user_id": "ab",
            "username": "ShortIdUser",
        }

        response = test_app.post("/session/start", json=payload)

        # user_id has min_length=3 in BaseRequestDTO
        assert response.status_code == 422

    def test_start_multiple_sessions(self, test_app):
        sessionIds = []
        for i in range(3):
            payload = {
                "user_id": f"test-user-{i:03d}",
                "username": f"User{i}",
            }
            response = test_app.post("/session/start", json=payload)
            data = response.json()
            assert data["status"] == "success"
            sessionIds.append(data["data"]["session_id"])

        # All session IDs must be unique
        assert len(set(sessionIds)) == 3


# ===============================================
#  TESTS: /session/end
# ===============================================

class TestEndSession:
    def test_end_session_success(self, started_session):
        client, sessionId = started_session

        payload = {
            "user_id": "test-user-001",
            "session_id": sessionId,
        }

        response = client.post("/session/end", json=payload)
        data = response.json()

        assert response.status_code == 200
        assert data["status"] == "success"
        assert data["action"] == "end_session"
        assert data["data"]["success"] is True

    def test_end_session_not_found(self, test_app):
        payload = {
            "user_id": "test-user-001",
            "session_id": "non-existent-session-id",
        }

        response = test_app.post("/session/end", json=payload)
        data = response.json()

        assert response.status_code == 200
        assert data["data"]["success"] is False
        assert "not found" in data["data"]["message"].lower()

    def test_end_session_twice(self, started_session):
        client, sessionId = started_session

        payload = {
            "user_id": "test-user-001",
            "session_id": sessionId,
        }

        # First end — should succeed
        response1 = client.post("/session/end", json=payload)
        assert response1.json()["data"]["success"] is True

        # Second end — session no longer exists
        response2 = client.post("/session/end", json=payload)
        assert response2.json()["data"]["success"] is False

    def test_end_session_missing_session_id(self, test_app):
        payload = {
            "user_id": "test-user-001",
        }

        response = test_app.post("/session/end", json=payload)

        assert response.status_code == 422


# ===============================================
#  TESTS: /session/message
# ===============================================

class TestMessageReceived:
    def test_message_received_success(self, started_session):
        client, sessionId = started_session

        payload = {
            "user_id": "test-user-001",
            "session_id": sessionId,
            "message": "Hello, how are you?",
        }

        response = client.post("/session/message", json=payload)
        data = response.json()

        assert response.status_code == 200
        assert data["status"] == "success"
        assert data["action"] == "message_received"
        assert data["data"]["success"] is True
        assert data["data"]["response"] != ""

    def test_message_received_invalid_session(self, test_app):
        payload = {
            "user_id": "test-user-001",
            "session_id": "non-existent-session-id",
            "message": "Hello?",
        }

        response = test_app.post("/session/message", json=payload)
        data = response.json()

        assert response.status_code == 200
        assert data["data"]["success"] is False

    def test_message_received_missing_message(self, test_app):
        payload = {
            "user_id": "test-user-001",
            "session_id": "some-session-id",
        }

        response = test_app.post("/session/message", json=payload)

        assert response.status_code == 422

    def test_message_received_missing_session_id(self, test_app):
        payload = {
            "user_id": "test-user-001",
            "message": "Hello?",
        }

        response = test_app.post("/session/message", json=payload)

        assert response.status_code == 422

    def test_message_received_after_session_ended(self, started_session):
        client, sessionId = started_session

        # End the session first
        endPayload = {
            "user_id": "test-user-001",
            "session_id": sessionId,
        }
        client.post("/session/end", json=endPayload)

        # Try to send a message to the ended session
        messagePayload = {
            "user_id": "test-user-001",
            "session_id": sessionId,
            "message": "Are you still there?",
        }
        response = client.post("/session/message", json=messagePayload)
        data = response.json()

        assert response.status_code == 200
        assert data["data"]["success"] is False

    def test_multiple_messages_same_session(self, started_session):
        client, sessionId = started_session

        messages = ["First message", "Second message", "Third message"]

        for msg in messages:
            payload = {
                "user_id": "test-user-001",
                "session_id": sessionId,
                "message": msg,
            }
            response = client.post("/session/message", json=payload)
            data = response.json()

            assert response.status_code == 200
            assert data["status"] == "success"
            assert data["data"]["success"] is True
