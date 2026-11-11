# Integrating the ai-agent into a web chat

Audience: a developer (or a Claude session) working in **another project**, a web with a built-in chat, that must send the user's messages to `ai-agent` and show its answers. It combines the API reference ([api.md](api.md)) with how to use the service from a web chat, and it describes **every field of every route**, so you can decide what to use and what to ignore. If the two documents disagree, `api.md` wins.

Written 2026-11-10 from `api.md`, `infrastructure/inbound/http/fastapi.py`, `application/inbound/dto/session.py`, `application/inbound/dto/base_request.py`, the vendored `contracts` wheel (`contracts.api.microservices.ai_agent.*`), `schema/response/general/full.schema.json` and `profiles/README.md`. Nothing here was run against a web client: the examples are checked against the code, not against a live call.

Contents: 1 What the service is · 2 Constraints · 3 The flow · 4 Conventions common to every call · 5 Routes (`start`, `message`, `end`, `health`, `available`) · 6 Profiles · 7 Chaining profiles and `output` · 8 Questions the agent asks · 9 Errors · 10 Backend example · 11 Checklist · 12 Known gaps

## 1. What the service is, and what a web chat does with it

- ai-agent is the "mind" of OBLIVION: it receives what the user said and returns **a text to say** (`data.response`). It never controls hardware: the robot's arm movements are returned as data (`directives`) for another service (Brain) to act on.
- A web chat only needs **three routes**: `POST /session/start`, `POST /session/message`, `POST /session/end`. The robot fields (`directives`, `gesture`, `speak_movements`) and the `movement` and `gesture` profiles are documented below so you know what they are, but a web chat ignores them.
- Port `7998` (`HTTP_ADDR`). Swagger UI at `/docs`. `GET /health` and `GET /available` are for monitoring; neither calls an LLM.

## 2. Read this before writing any code (constraints)

| Fact | Consequence for the web |
|---|---|
| **No authentication** in the service | Never expose it to the internet. The web's **backend** calls it; the browser never does |
| **No CORS** is configured (no CORS middleware in the code) | A browser cannot call it directly anyway. Put a proxy route in the web's backend (`/api/chat/...`) |
| Sessions live **in process memory**, no expiry, lost on restart | One session per chat conversation; be ready to recreate it (section 9) |
| One request = several LLM calls, one after another | Slow: expect several seconds up to tens of seconds. Use a long timeout (60 s or more) and show a "typing" state. There is **no streaming** |
| A failed message still answers **HTTP 200** (`status: "error"`) | Always read `status` and `data.success` / `data.error_code`, not only the HTTP status. Only a malformed body (**422**) and an unexpected crash (**500**) use another HTTP status (section 4.3) |
| The profile token is a check against a mistake, **not access control** | Keep it in the backend's secrets; the web's own login is what protects customer data |
| Data goes to the LLM providers and to Langfuse (when configured). The `dynamics` profile can reach Business Central customer data (personal columns masked first) | Decide which web users may reach it (section 6) |

## 3. The flow in one picture

```text
Browser  --(chat text)-->  Web backend  --POST /session/start-->    ai-agent   (once per conversation)
                                        <--session_id--
Browser  --(chat text)-->  Web backend  --POST /session/message-->  ai-agent   (every user message)
                                        <--data.response--
Browser  <--(answer)-----  Web backend
Browser  --(chat closed)-> Web backend  --POST /session/end-->      ai-agent
```

The web backend keeps the map `conversation id -> session_id`.

## 4. Conventions common to every call

### 4.1 Fields every request body carries (all three `/session/*` routes)

These come from the base request (`BaseRequestDTO`). **Unknown fields are rejected** (`extra="forbid"`, a 422): send only the fields documented here.

| Field | Type | Required | What it is and what it is used for |
|---|---|---|---|
| `user_id` | string, 3 to 128 characters | **Yes** | Who is talking. Use the web user's **stable** id (not an email that can change, nothing secret). It travels with the request through the service and is not checked against anything. Shorter than 3 or longer than 128 characters is a 422 |
| `request_id` | UUID string | No | An id for this one request. If you leave it out the service makes one. It names the message in the metrics, so send your own only if you want to match the call with your own logs |
| `correlation_id` | string | No | A tracing id to follow one user action across services. If you leave it out the service uses the one of the incoming trace headers. Useful when the web already has a request id per page action |
| `metadata` | object (any JSON) | No | Free data of the caller, carried with the request. **The service does not use it to decide anything**; leave it out unless you want it in the trace |
| `timestamp` | ISO 8601 date-time | No | When the caller built the request. Defaults to now (UTC). Leave it out |

### 4.2 The envelope of every answer

Every answer (from every route, including health) is:

```json
{ "action": "message_received", "status": "success", "status_code": 200, "message": "...", "data": { }, "timestamp": 1743850800.0 }
```

| Field | What it is |
|---|---|
| `action` | Which route answered: `start_session`, `end_session`, `message_received`, `health`, `check_availability` |
| `status` | `success`, or `error` when the request was understood but could not be carried out (or crashed). Show the user nothing from here |
| `status_code` | The same number as the HTTP status: `200` for success **and** for a handled failure of a message; `500` for a crash |
| `message` | A short technical text for logs. **Not for the user** |
| `data` | The useful part: the fields of each route below. `null` on a crash |
| `timestamp` | Seconds since 1970 (float) at which the answer was built |

### 4.3 HTTP status codes

| HTTP | When | Body |
|---|---|---|
| `200` | The request was valid. A message that could not be processed (`data.success: false`) is also `200`, with `status: "error"` | The envelope |
| `422` | The body does not match the model: a missing required field, a field of the wrong type, a value too long, an **unknown field**, `return` not `text` or `full` | FastAPI's own `{"detail": [...]}`, **not** the envelope. It is a bug in your request, not something to retry |
| `500` | An exception that was not handled | The envelope with `status: "error"`, `status_code: 500`, `data: null` and the error text in `message` |

## 5. Routes

| Method and path | Purpose | Use in a web chat |
|---|---|---|
| `POST /session/start` | Create a session and get its `session_id` | Once per conversation |
| `POST /session/message` | Send one user message and get the answer | Every user message |
| `POST /session/end` | End the session and free its memory | When the chat closes |
| `GET /health` | Liveness (is the process up) | Monitoring |
| `GET /available` | Is a model provider configured | Monitoring |
| `GET /docs` | Swagger UI (interactive description of the routes) | For developers |

### 5.1 `POST /session/start`

Creates a conversation. Body (the fields of 4.1 plus):

| Field | Type | Required | What it is and what it is used for |
|---|---|---|---|
| `username` | string | **Yes** | The person's display name. It is only stored with the session (in memory); no prompt, decision or trace reads it today |
| `email` | string | No | The person's email. Stored with the session like `username`; not validated and not used for anything today. Leave it out if you do not need it |
| `session_name` | string | No | The **title of the chat**, like the title of a chat in an online assistant. Its messages are grouped under that title in Langfuse. Blank text counts as none |

There is **no `profile` here**: the profile is chosen per message.

```json
{ "user_id": "web-user-123", "username": "Maria Lopez", "email": "maria@example.com", "session_name": "Chat 2026-11-10" }
```

Answer `data`:

| Field | Meaning |
|---|---|
| `success` | `true` when the session was created |
| `session_id` | **Keep it.** The id (a UUID string) to send with every message and with `end` |
| `message` | Technical text for logs (or `null`) |
| `error_code` | A code when `success` is `false`, otherwise `null` |

```json
{ "action": "start_session", "status": "success", "status_code": 200, "message": "Session started successfully.",
  "data": { "success": true, "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "message": null, "error_code": null }, "timestamp": 1743850800.0 }
```

### 5.2 `POST /session/message`

Sends one message of the user and returns the answer. It is the slow route (several LLM calls).

#### Request

Fields of 4.1 plus:

| Field | Type | Required | What it is and what it is used for | In a web chat |
|---|---|---|---|---|
| `session_id` | string | **Yes** | The id `start` returned. Unknown (service restarted, or already ended) gives `SESSION_NOT_FOUND` | Always |
| `message` | string | **Yes** | The text the user wrote, as typed. Do not add instructions or system text to it; the service already builds its own prompts and keeps the history of the session | Always |
| `profile` | string, max 64 | No | **Which recipe runs this message** (section 6). Leave it out: the `default` profile runs and needs no token. Naming a profile needs its `token` | Only to reach `dynamics` (or `special`) |
| `token` | string, max 256 | Required with any profile except `default` | The profile's secret, in plain text (the service hashes it and compares with the SHA-256 stored in the profile). A wrong or missing token, an unknown profile and a disabled profile all give the **same** `INVALID_PROFILE` answer. Never logged by the service; never log it yourself | Only with `profile`, from backend secrets |
| `client` | string, max 64 | No | A **name for the metrics** (which application is calling), e.g. `web-chat`. Written on every LLM call record and in Langfuse tags. Trust-based: nothing checks it | Yes, send `web-chat` |
| `pause_id` | string, max 64 | Only to answer a question | The id of the question this message answers, as the previous answer returned it in `data.pause_id` (section 8) | Only after a question |
| `return` | `"text"` or `"full"` | No | What the answer carries. `text`: only the speech (`response`). `full`: also `output`, the classification and plan of the run (section 7). Leave it out to get the profile's own default (`full` for `identification`, `text` for all the others). Any other value is a 422 | Leave out |
| `inputs` | object | Only for a profile that requires it | **Data a previous profile already found**, so this profile does not repeat that work (chaining, section 7). Never instructions: each field is read with the same code and checks as a model answer. Ignored when the message answers a question. A field the profile does not accept gives `INVALID_INPUT`; a missing required one gives `MISSING_INPUT` | Leave out |
| `speak_movements` | boolean, default `true` | No | A **robot** setting: whether the movement flow also words a short spoken line ("Turning my left arm 90 degrees") besides moving. Only matters for the `movement` profile | Leave out |

Minimal body (profile `default`, no token, no tools):

```json
{ "user_id": "web-user-123", "session_id": "a1b2c3d4-...", "message": "Hola, ¿qué puedes hacer?" }
```

Body that asks for a profile:

```json
{ "user_id": "web-user-123", "session_id": "a1b2c3d4-...", "message": "¿Qué pedidos abiertos tiene el cliente C00123?",
  "profile": "dynamics", "token": "<secret kept in the backend>", "client": "web-chat" }
```

#### Answer `data`

Fields that are **always** present:

| Field | Type | Meaning | In a web chat |
|---|---|---|---|
| `success` | boolean | `false` when the message could not be processed: unknown session, refused profile, bad input, LLM or tool failure. The envelope `status` is then `error` | Check it first |
| `response` | string | **The text to show the user.** Always speakable: it is an apology when `success` is `false`; a refusal or a question is also here. Empty only for a `movement` run that goes ahead with `speak_movements` off, or for a profile that has no text (`identification`) | **Show it** |
| `message` | string or null | The technical reason of a failure | Log it; **never show it** |
| `error_code` | string or null | A code that says which failure (section 9). `null` on success | Branch on it |
| `directives` | list | The arm movements to run, in order: each `{arm, degrees, direction, pause_seconds}`. See below | Ignore |
| `awaiting_user_input` | boolean | `true` when `response` is a **question**: the user's next message is its answer (section 8) | Handle it |
| `flow` | string or null | Which flow answered: `identification` (the triage), `conversation` (a plain reply), `special` (planning and tools), `movement` or `expression`. `null` when no flow ran (an early failure) | Logs |
| `gesture` | boolean | `true` when `directives` are an expressive gesture that goes with the reply, not movements the user asked for | Ignore |

Fields that appear **only when they apply**:

| Field | Appears when | Meaning |
|---|---|---|
| `profile` | The request named a profile | The profile that ran (an echo, useful for logs) |
| `output` | `return` is `full` (or the profile's default is) and the run has a `user_goal` | The classification and plan of the run as JSON (section 7). You can send it back as `inputs` to another profile |
| `pause_id` | `awaiting_user_input` is `true` and the request named a profile or a `pause_id` | The id to send back with the user's answer |
| `discarded_pause` | A waiting question was dropped | `true` when this message named a profile and had **no** `pause_id`, so the question that waited was thrown away |

`directives` items (robot data; the web does not run them):

| Field | Meaning |
|---|---|
| `arm` | `left` or `right` |
| `degrees` | Signed number of degrees (left 90 then left -90 brings the arm back) |
| `direction` | `forward` or `reverse` |
| `pause_seconds` | Seconds to wait after the previous movement ended before this one starts (0 = at once) |

Example success:

```json
{ "action": "message_received", "status": "success", "status_code": 200, "message": "...",
  "data": { "success": true, "response": "El cliente C00123 tiene 2 pedidos abiertos: ...", "message": null, "error_code": null,
            "directives": [], "awaiting_user_input": false, "flow": "special", "gesture": false, "profile": "dynamics" } }
```

Example handled failure (HTTP 200, `status: "error"`):

```json
{ "action": "message_received", "status": "error", "status_code": 200, "message": "Session ID not found.",
  "data": { "success": false, "response": "Sorry, I could not find this conversation. ...", "message": "Session ID not found.", "error_code": "SESSION_NOT_FOUND",
            "directives": [], "awaiting_user_input": false, "flow": null, "gesture": false } }
```

(The apology is written in English by the service and is abbreviated here: always show `data.response`, whatever it says. If the web needs another language, map `error_code` to your own text.)

### 5.3 `POST /session/end`

Ends a conversation. Body (the fields of 4.1 plus):

| Field | Type | Required | What it is and what it is used for |
|---|---|---|---|
| `session_id` | string | **Yes** | The session to end. After this the id cannot be used to send messages, and its history and any waiting question are dropped |

```json
{ "user_id": "web-user-123", "session_id": "a1b2c3d4-..." }
```

Answer `data`: `success` (`true` when it ended), `message` (technical text or `null`), `error_code` (`null`, or `SESSION_NOT_FOUND` when the session did not exist here). Call it when the user closes or resets the chat. `SESSION_NOT_FOUND` here is harmless.

### 5.4 `GET /health`

No body, no parameters. Answers as long as the process is up; **calls no LLM** and touches no external service.

```json
{ "action": "health", "status": "success", "status_code": 200, "message": "ai-agent is running", "data": { "healthy": true }, "timestamp": 1743850800.0 }
```

`data.healthy` is `true` whenever you get an answer. Use it for a liveness check.

### 5.5 `GET /available`

No body, no parameters. Checks only that **a model provider is configured** (a provider API key, or `OLLAMA_URL`). It **calls no LLM**, so it cannot tell whether a key is valid or out of quota. It does not depend on the MCP servers.

```json
{ "action": "check_availability", "status": "success", "status_code": 200, "message": "Availability checked successfully",
  "data": { "is_available": true, "reason": null }, "timestamp": 1743850800.0 }
```

| Field | Meaning |
|---|---|
| `is_available` | `true` when at least one provider is configured |
| `reason` | `null` when available; otherwise the text `no language model provider is configured` |

Use it for a readiness check ("can the assistant answer at all"), not as proof that the next message will succeed.

## 6. Profiles: which one should the web chat use?

A **profile** is a recipe: which steps run, which models answer, which tools may be used and which `inputs` are accepted. The service runs **one profile per message** and does not choose between them. Profiles are not listed by any route (so nobody can discover them); the set below is what exists today (`profiles/*.json`).

| Profile | What it does | Needs a token | Tools | `inputs` | Returns by default | Web chat? |
|---|---|---|---|---|---|---|
| (none) = `default` | Plans and answers general questions: triage, project manager, safety gate, action executor, draft writer, editor | **No** | none | none | `text` | **Yes, start here** |
| `dynamics` | The same steps as `special`, limited to the Business Central tools of `dynamics_microservice` (read-only: customers and orders) | Yes | only `dynamics_microservice` | none | `text` | **Yes**, for staff who may see customer data |
| `special` | The same steps with **every** configured MCP server | Yes | every configured server | none | `text` | Rarely |
| `chat` | A plain conversation reply (draft writer, editor), no planning | Yes | none | **requires** `user_goal` and `task_category` (accepts the rest of the classification) | `text` | Not alone (needs the output of `identification`) |
| `identification` | Only the triage: classifies the message (`output.task_category.domain` says what kind it is) | Yes | none | none | `full` | No (robot chain) |
| `movement` | Plans arm movements and validates them (motion planner, motion validator) | Yes | none | accepts the classification | `text` | **No** |
| `gesture` | Reads the emotion of a reply and builds random arm movements that go with it | Yes | none | **requires** `reply` (accepts `speech_seconds`) | `text` | **No** |

Recommendation:

1. **Start with no `profile`** (`default`): no token, nothing to set up.
2. Use `dynamics` for logged-in staff who may see customer/order data. Send its token from the backend only.
3. Do not chain profiles (`identification` then another) unless needed: the triage would run twice and every extra call costs time and money.

Profile behaviour to know:

- A request with a **profile** is checked: unknown, disabled, or wrong token gives `INVALID_PROFILE`.
- The tool profiles (`default`, `special`, `dynamics`) are bounded: `AI_AGENT_MAX_ATTEMPTS` (3), `AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE` (5) and a 60 s total wait for tools in one message. The history sent to the model is the last `AI_AGENT_HISTORY_TURNS` (6) turns of the session.
- The `dynamics` tools are read-only: `customer_orders`, `order_status`, `customer_card`, plus helpers (`get_guidance`, `list_workflows`, `get_job_result`, `cancel_job`). The service never sends an environment or a company; the Go service uses its defaults.

**Getting a token** (an operator of ai-agent does this once; the file holds a placeholder of zeros until then, so nothing can use the profile): generate a random token, put its SHA-256 in `profiles/<name>.json` (`token_sha256`), and give the token itself to the web's backend secrets. Command in `profiles/README.md`, section 3.

## 7. Chaining profiles, `inputs` and `output` (advanced, not needed for a web chat)

The robot's client (Brain) chains profiles: it asks `identification` with `return: full`, reads `output.task_category.domain`, and asks the profile that answers (`communication` -> `chat` with `inputs = output`; `movement` -> `movement`; anything else -> `special` or `dynamics`), then `gesture` with `inputs = {reply}` for a spoken reply. A web chat does not need this: `default` and `dynamics` classify and answer on their own.

`output` (when `return` is `full`) is the model's structured plan of the run, **without** `tokens_usage` and `raw`:

| Section | What it holds |
|---|---|
| `intent` | `primary` (`information_request`, `task_execution`, `content_generation`, `decision_support`, `clarification_request`, `system_operation`), `secondary` (list), `confidence` (0 to 1) |
| `user_goal` | `summary` (what the user wants) and `expected_outcome` |
| `task_category` | `domain` (`software`, `data`, `writing`, `design`, `research`, `operations`, `communication`, `system`, `movement`; it decides which flow answers), `type` (`analysis`, `design`, `generation`, `modification`, `validation`, `classification`, `orchestration`), `complexity` (`low`, `medium`, `high`) |
| `actions` | The plan: a list of actions, each with `id`, `description`, `action_type` (`analysis`, `generation`, `transformation`, `decision`, `retrieval`, `clarification`, `mcp_tool_call`), `dependencies`, `mcp_context` (`server_id`, `tool_name`, `parameters`), `required_inputs`, `output`, `error` |
| `missing_information` | What the user did not say: `field`, `why_needed`, `blocking` |
| `constraints` | `format` (`json`, `markdown`, `plain_text`, `code`, `table`), `language`, `tone` (`formal`, `neutral`, `casual`, `technical`), `length` (`short`, `medium`, `long`) |
| `safety_and_validation` | `sensitive` and `requires_confirmation` (booleans) |
| `next_step` | `ready_to_execute`, `status` (`proceed`, `awaiting_user_input`, `awaiting_confirmation`, `retry`, `error`, `complete`), `recommended_action`, optional `blocking_reason`, `requested_user_input`, `retry_action_id` |
| `mcp_routing` | `required_servers` |

`inputs` accepts **only** these structured fields (`intent`, `user_goal`, `mcp_routing`, `task_category`, `actions`, `missing_information`, `constraints`, `safety_and_validation`, `next_step`) and the plain values `reply` (text) and `speech_seconds` (number), and only those a profile lists in its own `inputs.requires` / `inputs.accepts`. Anything else is `INVALID_INPUT`. The model's token usage and raw text are always dropped.

## 8. When the agent asks a question

If `data.awaiting_user_input` is `true`, show `response` as a normal assistant message and remember `data.pause_id`.

- **With a profile** (`dynamics`, `special`): the user's **next** message must be sent with the **same `profile` and `token`** and `pause_id` set to the remembered id. The answer is judged (a real answer to the question, or something else) and the step that waited runs again. The id is used up; `inputs` is ignored; the token is checked again.
- **Without a profile** (`default`): a question is answered by simply sending the next message. No `pause_id` is needed (and none is returned unless the request named a profile or a `pause_id`).
- Only **one question waits per session**, and it is lost on a restart.
- If the user ignores the question and the next message is sent with a profile and **no** `pause_id`, the question is dropped (`discarded_pause: true`). That is fine, and it is how a user leaves a question.
- `PROFILE_MISMATCH` (the `pause_id` belongs to another profile) leaves the question waiting; `PAUSE_NOT_FOUND` (unknown, used, or nothing waits) means treat the message as a new one.

## 9. Errors and what the web does

Read `data.error_code` (the HTTP status is 200 for these):

| `error_code` | Meaning | Web behaviour |
|---|---|---|
| `SESSION_NOT_FOUND` | The session does not exist here (service restarted, or already ended) | **Start a new session and resend the message once.** Replace the stored `session_id`. The history of the old one is lost |
| `INVALID_PROFILE` | Unknown or disabled profile, or wrong/missing token (one generic answer for all, the reason is only in the service's log) | Configuration error: log it, show a generic apology. Do not retry |
| `MISSING_INPUT` | A required `inputs` field of the profile is missing (checked before any model call; `message` names the field) | A bug in the web's request. Log it |
| `INVALID_INPUT` | An `inputs` field the profile does not take, or one that is not valid (`message` names the field, never its content) | A bug in the web's request. Log it |
| `PROFILE_MISMATCH` | The `pause_id` belongs to a question of another profile | Use the same profile as the question |
| `PAUSE_NOT_FOUND` | The `pause_id` is not the waiting one | Send the message again as a new one (without `pause_id`) |
| `CONNECTION`, `TIMEOUT`, `AUTH`, `UNKNOWN`, ... | A real failure of that one message (LLM provider, network, tools) | Show `response` (an apology) and let the user retry. **Do not** reconnect or restart the session |

Only `SESSION_NOT_FOUND` is a reconnect signal. If the web cannot reach the service at all (connection refused, timeout), or gets a 422 or 500, show your own message ("The assistant is not available now") and do not loop.

## 10. Minimal backend example (TypeScript, Node 18+)

```ts
const AGENT = process.env.AI_AGENT_URL!;          // e.g. http://ai-agent:7998 (internal address)
const PROFILE = process.env.AI_AGENT_PROFILE;     // optional, e.g. "dynamics"
const TOKEN = process.env.AI_AGENT_TOKEN;         // only with a profile; never sent to the browser

async function post(path: string, body: object) {
  const r = await fetch(`${AGENT}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(90_000),          // the agent is slow
  });
  if (r.status === 422) throw new Error("bad request to ai-agent (a bug in this backend)");
  return (await r.json()).data;                   // read data.success / data.error_code
}

const sessions = new Map<string, string>();       // conversation id -> session_id (use a real store in production)
const pauses = new Map<string, string>();         // conversation id -> pause_id

async function ensureSession(conv: string, userId: string, username: string) {
  if (!sessions.has(conv)) {
    const d = await post("/session/start", { user_id: userId, username, session_name: `Chat ${conv}` });
    if (!d.success) throw new Error("agent unavailable");
    sessions.set(conv, d.session_id);
  }
  return sessions.get(conv)!;
}

export async function ask(conv: string, userId: string, username: string, text: string, retry = true): Promise<string> {
  const session_id = await ensureSession(conv, userId, username);
  const body: any = { user_id: userId, session_id, message: text, client: "web-chat" };
  if (PROFILE) { body.profile = PROFILE; body.token = TOKEN; if (pauses.has(conv)) body.pause_id = pauses.get(conv); }

  const d = await post("/session/message", body);

  if (!d.success && d.error_code === "SESSION_NOT_FOUND" && retry) {
    sessions.delete(conv); pauses.delete(conv);
    return ask(conv, userId, username, text, false);     // once
  }
  if (d.awaiting_user_input && d.pause_id) pauses.set(conv, d.pause_id); else pauses.delete(conv);
  return d.response;                                      // always safe to show
}
```

## 11. Checklist for the web project

- [ ] The backend, not the browser, calls ai-agent; its URL is an internal setting (`AI_AGENT_URL`).
- [ ] Only the web's own login decides who can chat; send the web user's stable id as `user_id` (3 to 128 characters).
- [ ] One `session_id` per conversation; recreate on `SESSION_NOT_FOUND` and resend once.
- [ ] Send only documented fields (an unknown field is a 422).
- [ ] Show `data.response`; never show `data.message` or `error_code` to users.
- [ ] Timeout of 60 to 90 s and a typing indicator; no streaming exists.
- [ ] Handle `awaiting_user_input` (and `pause_id` when a profile is used).
- [ ] Profile token (if any) only in backend secrets, never logged.
- [ ] Send `client: "web-chat"` so the metrics tell the web's calls apart.
- [ ] Call `/session/end` when the chat closes; use `/health` (alive) and `/available` (a provider is configured) for monitoring.
- [ ] Tell the ai-agent maintainer: the web's `client` name, and whether it needs `dynamics` (they must put the token's SHA-256 in `profiles/dynamics.json`) and the service's address reachable from the web backend.

## 12. Known gaps

- **No CORS and no auth**: both must be handled by the web backend or the network (an ai-agent change if ever needed, not in this document's scope).
- No streaming of the answer, no way to list profiles, sessions never expire (memory grows until `/session/end` or a restart).
- `profile`, `token`, `inputs`, `return`, `pause_id`, `client` and the answer fields `profile`, `output`, `pause_id`, `discarded_pause` are read by ai-agent from its own models: the vendored `contracts` wheel does not have them yet.
- Langfuse, when configured, receives the user's text and the model prompts and answers.
- `/session/end` drops the session from memory; whether the `metadata`, `correlation_id` or `request_id` of a request appear in a given trace is not covered here (see [monitoring](../operations/monitoring.md)).
