# HTTP API of the service

ai-agent answers over HTTP on port `7998` (`AI_AGENT_PORT`). Only **Brain** (`brain_microservice`) calls it, once per utterance. Everything below was checked against `infrastructure/inbound/http/fastapi.py` and `contracts.api.microservices.ai_agent.session`. Swagger UI is served at `/docs`.

The service **decides and answers**; it never controls hardware (see [ADR-002](../decisions/ADR-002-agent-decides-brain-acts.md)). It is not an MCP server: it is an MCP **client** (see [architecture](../architecture/architecture.md), section 10).

## Routes

| Method and path | Purpose | State |
|---|---|---|
| `POST /session/start` | Create a session (`username`, optional `email`, optional `session_name`) and get a `session_id` | Built |
| `POST /session/message` | Send `session_id` + `message` (+ `speak_movements`, default `true`) and get the answer | Built |
| `POST /session/end` | End the session | Built |
| `GET /health` | Liveness; calls no LLM | Built |
| `GET /available` | Whether a provider key or `OLLAMA_URL` is configured; calls no LLM, so it cannot tell if a key is valid | Built |
| `GET /docs` | Swagger UI | Built |

Every request carries a `user_id` (3 to 128 characters).

## Envelope

Every answer uses the same envelope, built in `infrastructure/inbound/http/responses.py`:

```text
action / status / status_code / message / data / timestamp
```

`data` is built from the `contracts.api.microservices.ai_agent.session.*` types of the bundled `contracts` wheel (`vendor/`, version in `requirements.txt`).

## `POST /session/message`

Request: `session_id`, `message`, `speak_movements` (Brain's setting, default `true`). The flow runs in a worker thread; one request is one `MessageFlowService`.

Answer (`AIAgentMessageResponse`):

| Field | Meaning |
|---|---|
| `success` | `false` when the message could not be processed (unknown session, LLM failure) |
| `response` | What to say. **Always speakable**: an apology when `success` is `false`. Empty only for a movement that goes ahead with `speak_movements` off; a refusal or a question is always said |
| `directives` | The movements to run, in order: `[{arm, degrees, direction}]`. `degrees` is signed (left 90 then left -90 returns the arm). Set by the movement flow, and by the expression flow with `gesture: true` |
| `awaiting_user_input` | `true` when `response` is a question: the next message of the session is its answer |
| `flow` | Which flow answered: `identification` (only when triage itself asks), `conversation`, `special` or `movement` |
| `message`, `error_code` | The technical reason of a failure and a code |

A gesture (`directives` with `gesture: true`, `pause_seconds` between movements) goes with a conversation or special reply when `AI_AGENT_EXPRESSION` is on. It is never required: if the expression flow fails or the validator refuses the gesture, the reply goes out without one. Brain starts it when the robot starts to speak. A movement the user asked for gets no gesture.

## Sessions

- Sessions are held **in process memory only** (`SessionService.sessions`). They are lost when the service restarts, and nothing expires them: they live until `/session/end`.
- Use one session per conversation, reused across utterances, so the history (`AI_AGENT_HISTORY_TURNS`) means something.
- `error_code == "SESSION_NOT_FOUND"` on `/session/message` or `/session/end` means exactly that the session no longer exists here: open a new one and, for a message, resend it once.
- Any other `error_code` (`CONNECTION`, `TIMEOUT`, `AUTH`, `UNKNOWN`, ...) is a real failure of that one message, not a reason to reconnect.

## Authentication

There is none in this service: it is called inside the OBLIVION workspace by Brain only. See [security](../security/security.md).
