# Monitoring and operations

## Probes

| Endpoint | Meaning |
|---|---|
| `GET /health` | Liveness. Calls no LLM and no dependency |
| `GET /available` | Readiness-like: a provider key or `OLLAMA_URL` is configured. It never calls an LLM, so a bad key or an unreachable provider is not detected |

## Logging and tracing

- `shared_logging` (`init_logging("ai-agent")`, `TracingMiddleware`, installed with `-e ../shared-logging`). Messages are constant strings with keyword fields. `LOG_LEVEL`, `LOG_FORMAT` and `TRACE_EXPORT_*` are read by that package (`shared-logging/docs/logging.md`).
- The trace headers are forwarded to the MCP servers (`infrastructure/outbound/mcp/client_manager.py`).
- Never log a provider key, a token or the content of `.env`.

## Metrics

`SessionMetrics` records tokens per phase, per model and per call for each message.

## Langfuse (optional)

Active when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set (`LANGFUSE_HOST` empty means the EU cloud).

- Each message is a trace and each LLM call a `generation` named after its step: model, tokens (thinking tokens included) and cost (`infrastructure/outbound/usage/prices.py`).
- **The generations also carry the payload sent and the answer received, so the user's text and the prompts reach Langfuse.** Use a project you trust with them, or leave the keys empty.
- A failure of the reporter never breaks a call.
- A chat can be named with `session_name` at `/session/start`: its messages are grouped under it.

## Failures and what the user hears

- A failed LLM call is retried up to `AI_AGENT_MAX_ATTEMPTS` unless the provider answered HTTP 400, 401, 403 or 404.
- A step whose answer says `retry` or `error` runs again up to the same limit.
- When it still fails, `/session/message` answers `success = false` with a speakable apology in `response` and the technical reason in `message`.

Categories (`application/orchestration/support/failure.py`): connection, timeout, rate limit, auth, not found, bad request, bad answer, unknown.

## Debugging

See [debugging-the-flow.md](debugging-the-flow.md): follow one message step by step, run one step many times, stop in a debugger.

## Known operational limits

- Sessions are lost on restart (see [api](../api/api.md)).
- No real LLM call has been made since the four-flow redesign; the only real run was `gemini-2.5-flash` on 2026-09-21. The configured profile was never run as a combination. Do one real call first (`tests/manual/full_flow_real_llm.py`; it costs money).
- stdio MCP servers (`fetch`, `filesystem`) are skipped with a warning, but the project manager is still told they exist, so it may plan an action that cannot run.
