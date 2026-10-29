# Configuration

Everything you can set, where, and what wins. Secrets live only in `.env` (never committed, never printed, never copied
into docs or tests); this file names variables and never shows a value.

## 1. Where settings come from

1. The process environment (what the deploy tool or your shell exports) always wins.
2. `.env` in the ai-agent folder, loaded at startup by `python-dotenv` with `override=False`. Copy `.env.example` to `.env`.
3. The code defaults listed below.
4. Files under `config/` (models, prices, budget) and `mcps/` (MCP servers).

`.env.example` and the code agree on every variable below; when you add one, add it to both and to this file. In the
OBLIVION workspace, `deployment/` regenerates its settings files from `.env.example`
(`deployment/scripts/env_inventory.py --write`).

## 2. Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `AI_AGENT_HOST` | `0.0.0.0` | bind address |
| `AI_AGENT_PORT` | `7998` | bind port |
| `AI_AGENT_RELOAD` | `1` | `1` = uvicorn auto-reload (development), `0` for a stable run (the deploy tool sets `0`) |
| `AI_AGENT_HISTORY_TURNS` | `6` | exchanges (a user message and its reply) remembered per session; only triage and the project manager read them |
| `AI_AGENT_PARALLEL_ACTIONS` | `1` | independent actions of a plan that run together (`1` = one by one; tool calls stay sequential). Keep `1` on providers with a tokens-per-minute limit |
| `AI_AGENT_MAX_ATTEMPTS` | `3` | tries (the first included) of a failed LLM call, MCP tool or `retry` answer |
| `AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE` | `5` | how many MCP tool actions one message may run; the rest are **not run** (failed with a reason that says the limit was reached, so their dependants are skipped) and the writer is told in the actions' errors. A whole number; `0` = no limit; not a whole number or negative = `5`, with a warning (never `0`). Retries of the same action do not count; actions that are not tool calls are not counted |
| `AI_AGENT_MCP_CALL_TIMEOUT_SECONDS` | `30` | seconds one MCP tool call may take (connect, initialize and the call). Keep it above the 20 s a slow query makes `dynamics_microservice` wait before it answers `running`. Not a positive number = `30`, with a warning. Listing the tools of a server keeps its own 10 s limit |
| `AI_AGENT_CHECK_MCP_<NAME>` | unset | `1` = optional reachability check of the MCP server `<NAME>` (its name in upper case, anything that is not a letter or a digit as `_`, for example `AI_AGENT_CHECK_MCP_DYNAMICS_MICROSERVICE`): it lists that server's tools, over the network, at start-up and on every `GET /available`, and **only logs** a warning naming the server when it is not reachable. `/available` answers the same either way; with this set the call takes up to 10 s per checked server. Unset or `0`: nothing is checked |
| `AI_AGENT_EXPRESSION` | `1` | `1` = the arm gesture that goes with a spoken reply (the expression flow: one more model call per reply); `0` = no gestures |
| `AI_AGENT_SPEECH_CHARS_PER_SECOND` | `14` | how fast the robot talks; the gesture lasts about as long as the reply takes to say at this rate |
| `AI_AGENT_EXPRESSION_SEED` | empty | a number makes the gestures repeatable (tests); empty = random |
| `AI_AGENT_MODELS_FILE` | `config/step_models.json` | another models file |
| `AI_AGENT_MODEL_PHASE_<n>` (n = 1..9, 20, 30, 99) | unset | model id for one phase; wins over the models file |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY`, `GROQ_API_KEY`, `COHERE_API_KEY` | empty | provider keys; set only the providers you use. `ANTHROPIC_API_KEY` is the key of the Claude profiles (`claude_haiku`, `claude_sonnet`). The default models are Google's, so `GOOGLE_API_KEY` is the one a default run needs (the free tier is enough). `GITHUB_PAT` and `GITHUB_API_KEY` are no longer read (GitHub Models is retired, ADR-012). `GET /available` is true when one of them or `OLLAMA_URL` is set |
| `GOOGLE_URL`, `MISTRAL_URL`, `GROQ_URL`, `COHERE_URL`, `OLLAMA_URL` | empty | OpenAI-compatible base URLs of those providers (`GITHUB_URL` is no longer read). No Mistral model can be chosen until an API id is verified, so `MISTRAL_API_KEY` and `MISTRAL_URL` are kept for it but unused. OpenAI and Anthropic are native and need no URL |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` | empty | optional reporting to Langfuse (section 5). Empty host = the EU cloud |
| `MCP_FILESYSTEM_DIR` | unset | folder mounted by `mcps/filesystem.json` (`${NAME}` is expanded in every `mcps/*.json`; a variable that is not set stays as written) |
| `DYNAMICS_MCP_URL` | unset | full URL (with its `/mcp` path) of the Streamable HTTP endpoint of `dynamics_microservice`, read by `mcps/dynamics_microservice.json`. A public IP and port over plain HTTP in the first stage. Never committed. Unset = that server is skipped with a warning |
| `LOG_LEVEL`, `LOG_FORMAT`, `TRACE_EXPORT_*` | see shared-logging | read by the shared logging package (`shared-logging/docs/logging.md`) |

Not settings any more: `AI_AGENT_FAST_PATH_ENABLED` (removed with the four-flow redesign: `task_category.domain` decides which
flow answers) and Brain's `AI_AGENT_FLOWS` (Brain makes one call per utterance). Brain's `AI_AGENT_SPEAK_MOVEMENTS` is
Brain's own setting and arrives with every message as `speak_movements`.

`GET /available` only checks that a provider key or `OLLAMA_URL` is configured. It never calls an LLM, so it cannot tell
whether the key is valid or the provider reachable.

## 3. Which model answers each step

Precedence for a phase, first match wins (`support/model_selection.py`, `choose`):

1. `AI_AGENT_MODEL_PHASE_<n>` in the environment;
2. `steps.<step name>` in the models file;
3. the active `profile`, entry for that step;
4. the `default` of the active profile;
5. the code default (`DEFAULT_MODEL` of the phase file: a Google model with a free tier, ADR-012: `gemini-3.1-flash-lite` for triage, data
   engineer, answer checker, clarification and emotion reader, `gemini-3.6-flash` for the others).

`config/step_models.json`:

```text
{ "profile": "<name>",          which profile is active
  "steps":   { "<step>": "<model id>" | null, ... },     per-step choice; null = the profile decides
  "profiles": { "<name>": { "default": "<id>", "<step>": "<id>", ... }, ... } }
```

Step names: `triage_specialist`, `project_manager`, `safety_quality_gatekeeper`, `cognitive_worker`, `mcp_operator`,
`data_engineer`, `draft_writer`, `editor_in_chief`, `answer_checker`, `user_clarification` and `motion_planner`. An unknown
step, profile or model fails at the first message, not silently. A model id must exist in
`domain/value_objects/llm_request/model_catalog.py`.

Profiles shipped: `proven` (**active since 2026-10-28**: every step on `gemini-3.1-flash-lite`, which has an end-to-end run of 2026-09-21 and answered 10 free-tier calls in a row; it replaces `gemini-2.5-flash`, which Google no longer gives to new keys), `budget`, `balanced`,
`quality`, `claude_haiku` (Claude through Anthropic's OpenAI-compatible endpoint, ADR-013: `claude-haiku-4-5` on every step and `claude-sonnet-5-5` for the planner; needs `ANTHROPIC_API_KEY`; run once on 2026-10-28; not active), `claude_mixed` (`claude-haiku-4-5` on every step except the planner, the draft writer and the editor, which use `claude-sonnet-5-5`; needs `ANTHROPIC_API_KEY`; run once on 2026-10-28 with all three messages right, about 2.5 times the cost of `claude_haiku`; not active), `claude_sonnet` (`claude-sonnet-5` on every step, for the Dynamics MCP epic, needs `ANTHROPIC_API_KEY`, untested, not active), `budget50_groq` (Groq models for planning, safety, worker, writer and editor, Google lite models elsewhere; needs a Groq key, not active),
and `google_free` (not active since 2026-10-28: `gemini-3.1-flash-lite` for triage, cleaning, checker, question and emotion reader, `gemini-3.6-flash` for the
other steps; Google models with a free tier, needs only `GOOGLE_API_KEY` and `GOOGLE_URL`; on the free tier `gemini-3.6-flash` returned 429 after about 7 calls in 30 s,
and Google uses free-tier content to improve its products; **untested as a combination**; decided in PR-004).

Change it without editing JSON:

```powershell
& windows\Scripts\python.exe tests\manual\show_models.py                              # what every step uses now, with its price
& windows\Scripts\python.exe tests\manual\show_models.py --step=project_manager       # every model for a step, cost per call and rating
& windows\Scripts\python.exe tests\manual\show_models.py --set=project_manager=<model id>
& windows\Scripts\python.exe tests\manual\show_models.py --clear=project_manager
& windows\Scripts\python.exe tests\manual\show_models.py --profile=<name>
```

`config/gemini_models.json`, `other_models.json` (prices and ratings), `budget.json` (the monthly budget) and
`measured_runs.json` feed the cost tools. `docs/models/gemini_models_per_step.md` and `docs/models/models_per_step_budget.md` are
**generated** from them (`show_models.py --write` and `--budget`); `docs/models/cost_of_a_full_plan.md` by
`tests/manual/estimate_cost.py --write`. Do not edit those three by hand. The cost and budget tables cover the text flows'
steps only; `motion_planner` can be set like any step and is left out of those tables.

## 4. MCP servers (`mcps/*.json`)

One file per server, `{ "<name>": { "type": ..., ... } }`. Servers of `type: sse` and `type: streamable_http` work (the transport is chosen by `type`; any other type is skipped with a warning). `aws_microservice` is `sse` (hardcoded
to `http://localhost:8080/mcp/sse`: edit the file when that service runs elsewhere; nothing uses it yet). The
`fetch` and `filesystem` servers are stdio (Docker), so they are skipped with a warning and never offer tools. The special
flow's project manager is still told which servers exist, so it may plan an action that cannot run (a known gap). Servers
that are unreachable offer no tools (listing times out after 10 s). A successful listing is kept for the life of the process; a **failed** one is not tried again for 60 s, so a server that is down costs one 10 s wait per minute, and one that comes back is picked up after that minute. A server that offers no tools is **left out for the message**: the planner is neither told it exists nor allowed to name it (`server_names`, `describe_servers`). That applies when the agent has a tools port (always, in the running service).

- `mcps/dynamics_microservice.json` is `streamable_http` and takes its URL from `DYNAMICS_MCP_URL`. No environment or company is configured or sent: the Go service uses its defaults (the sandbox).
- A server whose `url` still holds a `${NAME}` (the variable is not set) is **skipped with a warning** naming the server and the variable; the other servers keep working.
- `allowed_tools` (optional list in the server file): the catalog offers only those tools; any other tool the server lists is hidden, never callable, and logged as a warning with its name. A file without the list offers every tool. `mcps/dynamics_microservice.json` allows the three workflows and their helpers (`customer_orders`, `order_status`, `customer_card`, `get_guidance`, `list_workflows`, `get_job_result`, `cancel_job`).

## 5. Retries, failures and what the user hears

- An MCP **tool call** is tried once more (once, not `AI_AGENT_MAX_ATTEMPTS` times) only after a transport error (the server could not be reached or the connection broke) or `error (retry_later)`. A timeout, `error (input)`, `error (not_found)`, `error (source_problem)` and `error (internal)` are final. A timeout says so in its message, so the planner can tell it from a tool error. The retry is logged with the tool name and the reason only, never an argument or an answer. The tool calls of one message may wait **60 s in total** (a fixed budget, not a setting: `MAX_TOOL_WAIT_SECONDS` in `action_executor.py`), the follow-up of a query that is still running included: each call gets what is left of it, and when nothing is left the call is not made and answers a timeout. When a tool failed for good (including a retry that failed again), the step that used it is **not asked again** by the action loop, whatever `AI_AGENT_MAX_ATTEMPTS` says; a step that produced nothing for another reason still is.
- A failed LLM call is retried up to `AI_AGENT_MAX_ATTEMPTS` unless the provider answered HTTP 400, 401, 403 or 404 (a bad request, bad credentials, not allowed, unknown model: trying again cannot help).
- A step whose answer says `retry` or `error` runs again, up to the same limit.
- When it still fails, `/session/message` answers `success = false` with a speakable apology in `response` (what happened, in
  which activity, why) and the technical reason in `message`.
- `error_code = SESSION_NOT_FOUND` means the session does not exist here (sessions are in process memory only and are lost
  when the service restarts): the caller opens a new session and resends the message once.

## 6. Langfuse (optional)

With both keys set, every message is a trace and every LLM call a `generation` (model, tokens with the thinking tokens
counted, cost from `infrastructure/outbound/usage/prices.py`). **The generations also carry the payload sent and the answer
received, so the user's text and the prompts reach Langfuse.** Use a project you trust with them, or leave the keys empty.
A failure of the reporter never breaks a call. A chat can be named with `session_name` at `/session/start`: its messages
are grouped under it.
