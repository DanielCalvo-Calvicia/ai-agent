# infrastructure/inbound/http/

The HTTP API of ai-agent (port `AI_AGENT_PORT`, 7998).

| File | Contents |
|---|---|
| `fastapi.py` | `SessionFastAPI`: registers `POST /session/start`, `POST /session/message`, `POST /session/end`, `GET /health` and `GET /available` (plus FastAPI's `/docs`). Each route turns the body into a DTO, calls the `SessionInboundPort` (the message route in a worker thread, because the flow is blocking), and turns the result into the contract answer (`contracts.api.microservices.ai_agent.session`, `MotorDirective` for the movements). `/available` only checks that a provider is configured; it never calls an LLM. |
| `responses.py` | `success` and `failure`: build the JSON answer as the project's `ApiEnvelope` (`action / status / status_code / message / data / timestamp`), the same shape as every other OBLIVION service. A request understood but not carried out still answers HTTP 200; callers must read the envelope's `status` and `data.success`. |

## How it works in the project

`composition_root/main.py` creates the FastAPI app and one `SessionService`, then `SessionFastAPI(app, session_service, availability_check)` registers the routes. Errors with an `error_code` (`SESSION_NOT_FOUND`, `INVALID_PROFILE`, `MISSING_INPUT`, `INVALID_INPUT`, `PROFILE_MISMATCH`, `PAUSE_NOT_FOUND`) come from the service; the adapter only passes them on. Tracing uses `shared_logging`'s `TracingMiddleware`.

Any change to a route, a field or an `error_code` must update `docs/api/api.md` and `docs/requirements/requirements.md`.
