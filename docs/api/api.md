# HTTP API of the service

ai-agent answers over HTTP on port `7998` (`HTTP_ADDR`). Only **Brain** (`brain_microservice`) calls it, once per utterance. Everything below was checked against `infrastructure/inbound/http/fastapi.py` and `contracts.api.microservices.ai_agent.session`. Swagger UI is served at `/docs`.

The service **decides and answers**; it never controls hardware (see [ADR-002](../decisions/ADR-002-agent-decides-brain-acts.md)). It is not an MCP server: it is an MCP **client** (see [architecture](../architecture/architecture.md), section 10).

## Routes

| Method and path | Purpose | State |
|---|---|---|
| `POST /session/start` | Create a session (`username`, optional `email`, optional `session_name`) and get a `session_id` | Built |
| `POST /session/message` | Send `session_id` + `message` (+ `speak_movements`, default `true`; + `profile`, `token`, `inputs`, `return`, `pause_id`, `client`, see below) and get the answer | Built |
| `POST /session/end` | End the session | Built |
| `GET /health` | Liveness; calls no LLM | Built |
| `GET /available` | Whether a provider key or `OLLAMA_URL` is configured; calls no LLM, so it cannot tell if a key is valid. Its answer does not depend on the MCP servers; `AI_AGENT_CHECK_MCP_<NAME>=1` only makes it log (see [monitoring](../operations/monitoring.md)) | Built |
| `GET /docs` | Swagger UI | Built |

Every request carries a `user_id` (3 to 128 characters).

## Envelope

Every answer uses the same envelope, built in `infrastructure/inbound/http/responses.py`:

```text
action / status / status_code / message / data / timestamp
```

`data` is built from the `contracts.api.microservices.ai_agent.session.*` types of the bundled `contracts` wheel (`vendor/`, version in `requirements.txt`).

## `POST /session/message`

Request: `session_id`, `message`, `speak_movements` (Brain's setting, default `true`) and, since T-05.9, these **optional** fields (the vendored `contracts` wheel does not have them yet: ai-agent reads them from its own request model, `application/inbound/dto/session.py`, until the maintainer changes the `contracts` repository):

| Field | Meaning |
|---|---|
| `profile`, `token` | The profile asked and its token. No `profile`: the `default` profile, which needs no token. The token is the plain text; the service compares its SHA-256 with the one of the profile. Never logged |
| `inputs` | An object: the fields the profile takes, as the previous profile returned them (`output`), or `reply` for `gesture`. Data, never instructions: each field is read with the code that reads an LLM answer and the domain checks; `tokens_usage` and `raw` are ignored; ignored on the answer to a question |
| `return` | `"text"` (only `response`, as always) or `"full"` (also `output`). None: the `default_return` of the profile (`identification`: `full`; the rest: `text`) |
| `pause_id` | The id of the question this message answers |
| `client` | A name for the metrics (trust-based; used from T-05.15) |

`/session/start` takes **no** profile. A body with none of these fields gets exactly the answer it always got, and runs `default`.

Answer (`AIAgentMessageResponse`, plus the fields of a profile request, which appear only when they apply):

| Field | Meaning |
|---|---|
| `success` | `false` when the message could not be processed (unknown session, refused profile, bad input, LLM failure) |
| `response` | What to say. **Always speakable**: an apology when `success` is `false`. Empty only for a movement that goes ahead with `speak_movements` off, or for a profile with no text (`identification`); a refusal or a question is always said |
| `directives` | The movements to run, in order: `[{arm, degrees, direction}]`. `degrees` is signed (left 90 then left -90 returns the arm). Set by the `movement` profile, and by the `gesture` profile with `gesture: true` |
| `awaiting_user_input` | `true` when `response` is a question: the next message of the session is its answer |
| `flow` | Which flow answered: `identification`, `conversation`, `special`, `movement` or `expression` (the flow of the profile that ran) |
| `message`, `error_code` | The technical reason of a failure and a code |
| `profile` | The profile that ran. Only when the request named one |
| `output` | The `Response` of the run as JSON, in the shape of the sections of an LLM answer (`intent`, `user_goal`, `task_category`, `actions`, ...), **without** `tokens_usage` and `raw`. Only when `return` is `full` (or the profile's default is) and the run has a `user_goal`; send it back as `inputs` |
| `pause_id` | Only when `awaiting_user_input` is `true` and the request named a profile or a `pause_id`: send it back with the answer |
| `discarded_pause` | `true` only when a question that was waiting was dropped because this message had a profile and no `pause_id` |

**Errors** (`success: false`, status `error`, the transport status is 200 like every error of this route; read `data.error_code`):

| `error_code` | When | Notes |
|---|---|---|
| `INVALID_PROFILE` | the profile does not exist, is disabled, or its token is missing or wrong | **One generic answer for all of these**: the message never says which, so a client cannot find out which profiles exist. The reason is only in the service's log. Profiles are never listed |
| `MISSING_INPUT` | a required input of the profile is missing | Before any model call. The message names the field |
| `INVALID_INPUT` | an input the profile does not take, or one that is not valid | Added in T-05.9 (not in PR-005): the message names the field, never its content |
| `PROFILE_MISMATCH` | the `pause_id` belongs to a question of another profile | The question stays waiting and keeps its `pause_id` |
| `PAUSE_NOT_FOUND` | the `pause_id` is not the waiting one (unknown, used, or nothing waits) | Treat the message as a new one |
| `SESSION_NOT_FOUND` | the session does not exist | As before |

**A question the user must answer.** When a run asks the user (`awaiting_user_input: true`) and the request named a profile, the answer carries a `pause_id`. Send the answer with the **same profile** and that `pause_id`: the answer is judged and the step that waited runs again (`inputs` is ignored; the token is checked again; the id is consumed). One question waits per session; it is lost when the service restarts. A message that names a profile and has **no** `pause_id` is a new message: the waiting question is discarded (`discarded_pause: true`), which is also how a user leaves a question. A **legacy** request (no `profile` and no `pause_id`) still answers the waiting question, as before: a client that does not know the new fields keeps working.

**Which profile (the client's rule, not the service's).** The service runs ONE profile per message and never chooses between flows. The steps of each profile (PR-005 section 11, `profiles/README.md`):

| Profile | Steps | Tools | Inputs (required) | Returns by default |
|---|---|---|---|---|
| `identification` | triage | none | none | `full` |
| `chat` | draft writer, editor | none | `user_goal`, `task_category` (accepts the rest of the classification) | `text` |
| `special` | triage, project manager, safety gate, action executor, draft writer, editor | every configured MCP server | none | `text` |
| `dynamics` | the same as `special` | only `dynamics_microservice` | none | `text` |
| `default` | the same as `special` | none | none | `text` |
| `movement` | motion planner, motion validator | none | none (accepts the classification) | `text` |
| `gesture` | emotion reader, gesture builder | none | `reply` (accepts `speech_seconds`) | `text` |

A client that wants the old behaviour chains them: ask `identification` with `return: full`; read `output.task_category.domain`; `communication` -> `chat` with `inputs = output`; `movement` -> `movement`; anything else -> `special` or `dynamics` (they classify again: the service allows it and says nothing, so a client that wants to avoid the extra call asks them directly); then `gesture` with `inputs = {reply}` for a spoken reply (not after `movement`). `tests/brain_chain.py` is that chain, in the tests.

The flow runs in a worker thread; one request is one `MessageFlowService`.


## Sessions

- Sessions are held **in process memory only** (`SessionService.sessions`). They are lost when the service restarts, and nothing expires them: they live until `/session/end`.
- Use one session per conversation, reused across utterances, so the history (`AI_AGENT_HISTORY_TURNS`) means something.
- `error_code == "SESSION_NOT_FOUND"` on `/session/message` or `/session/end` means exactly that the session no longer exists here: open a new one and, for a message, resend it once.
- Any other `error_code` (`CONNECTION`, `TIMEOUT`, `AUTH`, `UNKNOWN`, ...) is a real failure of that one message, not a reason to reconnect.

## Tools consumed (`dynamics_microservice`)

ai-agent is a **client** of the MCP endpoint of `dynamics_microservice` (Go, read-only). The source of truth is that project: `docs/api/mcp.md` and `docs/decisions/ADR-025-mcp-inbound-adapter.md` (outside this repository; ai-agent never modifies them). What ai-agent depends on, [ADR-011](../decisions/ADR-011-mcp-streamable-http.md) for why:

| | |
|---|---|
| Transport | Streamable HTTP, `POST` to the URL in `DYNAMICS_MCP_URL` (it ends in `/mcp`), stateless, plain JSON, one session per call; no authentication; trace headers forwarded |
| Tools offered to the planner | `customer_orders` (`customer_no`, `scope`, `since`), `order_status` (`customer_no`, `order_no`), `customer_card` (`customer_no`), the SEUR shipment tools `shipment_tracking` (`customer_no`, `page`, `size`: the shipments of a customer, one page), `order_shipments` (`order_no`, optional `customer_no`: the shipments of an order) and `shipment_status` (`shipment_no`: one shipment) (T-07.10), and the helpers `get_guidance`, `list_workflows`, `get_job_result` (`job_id`, `offset_rows`, `limit_rows`), `cancel_job` (`job_id`). All read-only. The list is `allowed_tools` in `mcps/dynamics_microservice.json`; the generic tools (`list_tables`, `describe_table`, `plan_query`, `run_query`) are never offered |
| Never sent | `environment` and `company`: the Go service uses its defaults |
| An answer | since 2026-11-11 (the jobs contract of the Go service, `docs/api/mcp.md` there): a first line `status: ok \| running \| error`, then `returned`, `total`, `complete`, `coverage`, optionally `hint`, a blank line and a table of text delimited with `\|`, at most 500 rows and 64 KB. A query not done after the service's own wait (about 25 s) answers `status: running` with a `job_id` and `retry_after_seconds` and no table; a several-table answer repeats `status` (and `job_id`) in the block of each table under its `## title`. The older shape (`note: pending: … job <id> …`) stays in the Go service until at least 2027-01-11 |
| An error | a tool error (`isError`) whose text, since 2026-11-11, starts with `status: error` and has the line `error (<kind>): <message>` second, kind `input`, `not_found`, `retry_later`, `source_problem` or `internal` |
| What ai-agent does with them | a call is limited to `AI_AGENT_MCP_CALL_TIMEOUT_SECONDS` and the calls of one message to 60 s in total; one retry only after a transport error or `retry_later`; an answer that carries a job is followed to its result **by the MCP adapter in code** (T-07, ADR-018; not by a model): the `job_protocol` of the server file (`dynamics_v1` for this service, `dynamics_pending` for the older shape, `none` for a server with no jobs) finds the job of each table, the adapter reads each with `get_job_result` (a wait of 1 s doubling to 5 s between reads, inside the 60 s of the message) and the answer the operator gets is the final one. With several jobs in one answer it is **all or nothing**: if one does not end in time the ones still running are cancelled with `cancel_job` and no table is given, only a plain "still running"; an answer that cannot be understood fails that action with a reason. A result that is a first page (`complete: no`, `next_offset`) is given as it is with its hint: the other pages are not read; no row limit of its own |

The names and parameters are pinned by a snapshot, `tests/fixtures/dynamics_tools_snapshot.json`, taken from those documents; a test checks that every allowed tool is in it and that the local fake server used by the tests has the same parameters. **Refresh it by hand** from the real `tools/list` when the Go project changes or at the first real run (T-01.9).

## Authentication

There is none in this service: it is called inside the OBLIVION workspace by Brain only. See [security](../security/security.md).
