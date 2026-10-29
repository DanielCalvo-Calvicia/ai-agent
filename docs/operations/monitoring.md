# Monitoring and operations

## Probes

| Endpoint | Meaning |
|---|---|
| `GET /health` | Liveness. Calls no LLM and no dependency |
| `GET /available` | Readiness-like: a provider key or `OLLAMA_URL` is configured. It never calls an LLM, so a bad key or an unreachable provider is not detected. It answers the same whatever happens to the MCP servers; with `AI_AGENT_CHECK_MCP_<NAME>=1` it also lists that server's tools (up to 10 s) and only logs a warning when it is not reachable |

## Logging and tracing

- `shared_logging` (`init_logging("ai-agent")`, `TracingMiddleware`, installed with `-e ../shared-logging`). Messages are constant strings with keyword fields. `LOG_LEVEL`, `LOG_FORMAT` and `TRACE_EXPORT_*` are read by that package (`shared-logging/docs/logging.md`).
- The trace headers are forwarded to the MCP servers (`infrastructure/outbound/mcp/client_manager.py`).
- Never log a provider key, a token or the content of `.env`.
- The libraries under the MCP client are kept at WARNING whatever `LOG_LEVEL` says (`quiet_client_libraries()` in `infrastructure/outbound/mcp/client_manager.py`, applied at import and again after `init_logging`): `httpx` logs the full URL of every request at INFO, `httpcore` the address it connects to and `mcp.client` the whole message it sends (the tool arguments) at DEBUG. A test fails if any of them reaches a log again.
- A failed MCP listing is logged once per minute at most, with the server name and the **class** of the error (`error_type`), never its text, traceback or URL. The optional check (`AI_AGENT_CHECK_MCP_<NAME>=1`) logs `MCP server is not reachable or offers no tools` with the server name, at start-up and on `/available`.

## Metrics

`SessionMetrics` records tokens per phase, per model and per call for each message, and, next to them, the **MCP tool calls** of the message (`tool_calls` in `summary()`): for each one the tool name, the outcome, the duration in ms and the number of tries (a retry makes it 2; 0 means no server offered the tool). The outcome is one of `ok`, `timeout`, `input`, `not_found`, `retry_later`, `source_problem`, `internal`, `transport` (a call cut short by the 60 s the tool calls of a message share, or not made because nothing was left, is a `timeout`, with 0 tries in the second case): a tool error is read from the text `error (<kind>): ...` the Go service sends, and anything else is `internal`. **Never an argument or an answer.** Each call also leaves one log line, `MCP tool call` (`tool_name`, `outcome`, `duration_ms`, `attempts`). A tool call is only counted in the metrics when it happens inside an MCP step of the special flow; a call made anywhere else is still logged.

## Langfuse (optional)

Active when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set (`LANGFUSE_HOST` empty means the EU cloud).

- Each message is a trace and each LLM call a `generation` named after its step: model, tokens (thinking tokens included) and cost (`infrastructure/outbound/usage/prices.py`).
- **The generations also carry the payload sent and the answer received, so the user's text and the prompts reach Langfuse.** Use a project you trust with them, or leave the keys empty.
- Each MCP tool call is a `span` named after the tool, child of the message's root span, with the outcome, the duration (ms) and the tries as metadata, **no input and no output**, and level `ERROR` when the outcome is not `ok`.
- A failure of the reporter never breaks a call.
- A chat can be named with `session_name` at `/session/start`: its messages are grouped under it.

## MCP tool calls: what slow and failing look like

| What you see | What it means |
|---|---|
| `MCP tool call` with a large `duration_ms` | a slow query; the Go service answers `status: running` after its own 20 s wait and the operator follows up once; every call is also in `SessionMetrics.tool_calls` and in Langfuse |
| outcome `timeout`, `attempts` 1 | the call hit `AI_AGENT_MCP_CALL_TIMEOUT_SECONDS` (30 s) or what was left of the 60 s of the message; never retried |
| outcome `timeout`, `attempts` 0 | no wait was left for this message: the call was not made |
| outcome `transport`, `attempts` 2 | the server could not be reached or the connection broke, once more tried |
| outcome `retry_later`, `attempts` 2 | the source failed for now, tried twice |
| outcome `input`, `not_found`, `source_problem`, `internal` | a tool error of that kind, never retried; the step is not asked again |
| warning `MCP tool failed for good, not asking again` | the action loop stopped re-asking the model after such a failure |
| warning `MCP action not run: the limit per message was reached` | `AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE`; the writer tells the user |
| warning `MCP tool is not in allowed_tools, hiding it` | the server offers a tool the server file does not allow (for example a generic tool) |
| warning `MCP server url is not set, ignoring the server` | `DYNAMICS_MCP_URL` is not set |
| warning `Could not list MCP tools` (once a minute at most) | a server is down; the planner is not shown it and the reply says the data cannot be reached now |

What the user hears for a tool that failed is one honest sentence per kind, written by the last steps of the flow (see the prompts in [schemas-and-prompts](../rules/schemas-and-prompts.md)); an apology of the failure categories below is only for the language model, not for a tool.

## Failures and what the user hears

- A failed LLM call is retried up to `AI_AGENT_MAX_ATTEMPTS` unless the provider answered HTTP 400, 401, 403 or 404.
- A step whose answer says `retry` or `error` runs again up to the same limit.
- When it still fails, `/session/message` answers `success = false` with a speakable apology in `response` and the technical reason in `message`.

Categories (`application/orchestration/support/failure.py`): connection, timeout, rate limit, auth, not found, bad request, bad answer, unknown.

## Debugging

See [debugging-the-flow.md](debugging-the-flow.md): follow one message step by step, run one step many times, stop in a debugger.

## Known operational limits

- The timeout of the **caller** of ai-agent (Brain, or a web chat) is `UNKNOWN` until it is measured at T-01.9; a message that follows up a slow query can take up to 60 s of tool waiting plus the model calls. Write the measured value here.
- The Dynamics tools were run only with scripted LLMs and a local fake of the service: nothing says yet how long a real message takes, what it costs or whether a real model follows a `running` answer up.

- Sessions are lost on restart (see [api](../api/api.md)).
- One real run since the four-flow redesign (2026-10-28, T-02.10): three messages on `gemini-3-flash-preview` through `tests/manual/chat_session.py`, 10 calls, 18,203 tokens, correct answers; the active profile could not finish that day (Google 503 "high demand" on `gemini-3.1-flash-lite`: a failing call is retried 3 times with no wait, and one failing message took minutes). The configured profile was never run on a whole message.
- stdio MCP servers (`fetch`, `filesystem`) are skipped with a warning, but the project manager is still told they exist, so it may plan an action that cannot run.
