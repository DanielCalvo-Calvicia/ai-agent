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
| `AI_AGENT_MODELS_FILE` | `config/step_models.json` | another models file |
| `AI_AGENT_MODEL_PHASE_<n>` (n = 1..9, 20, 99) | unset | model id for one phase; wins over the models file |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY`, `GROQ_API_KEY`, `COHERE_API_KEY`, `GITHUB_PAT` | empty | provider keys; set only the providers you use. `GET /available` is true when one of them or `OLLAMA_URL` is set |
| `GOOGLE_URL`, `MISTRAL_URL`, `GROQ_URL`, `COHERE_URL`, `GITHUB_URL`, `OLLAMA_URL` | empty | OpenAI-compatible base URLs of those providers. OpenAI and Anthropic are native and need no URL |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` | empty | optional reporting to Langfuse (section 5). Empty host = the EU cloud |
| `MCP_FILESYSTEM_DIR` | unset | folder mounted by `mcps/filesystem.json` (`${NAME}` is expanded in every `mcps/*.json`; a variable that is not set stays as written) |
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
5. the code default (`DEFAULT_MODEL` of the phase file: a **GitHub Models** id, a retired service, so in practice you always
   set one of the above).

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

Profiles shipped: `proven` (every step on `gemini-2.5-flash`, the only model tested end to end), `budget`, `balanced`,
`quality`, and `budget50_groq` (active at the time of writing: Groq models for planning, safety, worker, writer and editor,
Google lite models elsewhere, **untested as a combination**).

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

One file per server, `{ "<name>": { "type": ..., ... } }`. Only `type: sse` servers work: `aws_microservice` (hardcoded
to `http://localhost:8080/mcp/sse`: edit the file when that service runs elsewhere; the Go service is unused today). The
`fetch` and `filesystem` servers are stdio (Docker), so they are skipped with a warning and never offer tools. The special
flow's project manager is still told which servers exist, so it may plan an action that cannot run (a known gap). Servers
that are unreachable offer no tools (the catalog times out after 10 s and is cached).

## 5. Retries, failures and what the user hears

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
