# ai-agent

The "mind" of OBLIVION. It receives what the user said (text) and runs it through a chain of LLM calls that plan, check, execute and write a reply. It never controls hardware. `brain_microservice` calls it and then acts on the answer (speaks it, moves the arms). It hosts several agents, called **flows**: **conversation-flow** writes the reply and **motion-flow** decides the arm movements (an ordered list). They never call each other: Brain asks motion-flow first, then conversation-flow with what motion-flow decided.

Status: **prototype. Tried with a real LLM (Gemini) end to end on a simple request. The default provider, GitHub Models, is retired, so set the models with `AI_AGENT_MODEL_PHASE_<n>` (see `docs/orchestrator_decisions.md`).** Read [Known problems and decisions](#known-problems-and-decisions) before wiring it in.

- Port: `7998` (`AI_AGENT_PORT`)
- Stack: Python, FastAPI, hexagonal layout, LLM access through `ai_sdk`, MCP client
- Logging: `shared-logging`

## What it does, in one picture

```text
POST /<flow>/session/message  ->  SessionService  ->  MessageFlowService  ->  Pipeline.run()  (one Flow per agent)

conversation-flow:
   1 Triage -> 2 Project manager -> 3 Safety gate -> 4/5/6 Action executor -> 7 Draft writer -> 8 Editor -> reply text
       |                |                    |
       +-- needs user input? (after 1, 2 or 3) --> ask the user, stop here

motion-flow:
   1 Triage (shared) -> 20 Motion planner -> 21 Motion validator (plain code) -> list of movements
                              +-- a detail is missing? --> ask the user, stop here
```

Every phase is one (or several) LLM calls through `LLMOutboundPort`. Each phase has a system prompt (`prompts/<id>_<name>.txt`, named in the phase's own file) and a JSON Schema for its answer (`schema/response/advanced/`). Today the service returns **a plain text reply** (`user_goal.expected_outcome` after phase 8), not the full structured decision.

## What the agent knows

Every phase gets, before its own instructions: the generic rules, `prompts/capabilities.txt` (what the robot can and cannot do; edit it to change that) and the current date and time.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/conversation-flow/session/start` | Create a session (`username`, optional `email`) and get a `session_id` |
| POST | `/conversation-flow/session/message` | Send `session_id` + `message` (optionally `robot_context`, what motion-flow decided), get the reply in `data.response` |
| POST | `/conversation-flow/session/end` | End the session |
| POST | `/motion-flow/session/start` \| `message` \| `end` | The same three routes for motion-flow. `message` answers `data.directives` (`[{arm, degrees, direction}]` in execution order), `data.response` (a refusal or a question, to be spoken) and `data.awaiting_user_input` |
| POST | `/session/start` \| `message` \| `end` | **Deprecated** alias of conversation-flow's routes (same sessions), kept until no caller uses it |
| GET | `/health` | Liveness (does not call any LLM) |
| GET | `/available` | Whether a provider key (or `OLLAMA_URL`) is configured (does not call any LLM) |
| GET | `/docs` | Swagger UI |

Responses use the envelope `action / status / status_code / message / data / timestamp`. When a message is not processed (unknown session, LLM failure), `status` is `"error"`, `data.success` is `false`, `data.response` is an apology that says what happened, in which step and why (it can be spoken), and the technical reason is in `data.message`.

## Session lifecycle

Sessions (`SessionService.sessions`) are held **in process memory only** — nothing is persisted, so every session is lost when ai-agent restarts. The intended usage for a caller like Brain is one session per *conversation*, reused across many separate voice-pipeline runs (not one session per utterance), so the per-session history (`AI_AGENT_HISTORY_TURNS`) actually means something. Nothing here evicts or expires a session on its own: it lives until `/session/end` is called or the process restarts.

Because of that, a caller holding a session id across ai-agent restarts must be ready for it to vanish. `/session/message` and `/session/end` report this the same way: `data.success = false` and `data.error_code = "SESSION_NOT_FOUND"` (`data.response` is still a speakable apology). That combination specifically means "this session no longer exists here" — the caller's own move is to call `/session/start` again and, for a failed `/session/message`, resend the same message once against the new session id. Any other `error_code` (a classified failure, e.g. `"CONNECTION"`, `"TIMEOUT"`, `"AUTH"`, `"UNKNOWN"`; see `application/orchestration/failure.py:classify`) is a real failure of that one message, not a reason to start a new session.

## How each part works

### Composition root: `composition_root/main.py`
Changes to the project root, loads `.env` (`python-dotenv`; variables already set in the environment win), builds the MCP tool executor from `mcps/*.json`, creates `VercelAIAdapter` from `VercelAIConfig.from_env(...)`, passes both to `SessionService`, registers the routes in `SessionFastAPI` and adds `TracingMiddleware`. Runs uvicorn on `AI_AGENT_HOST:AI_AGENT_PORT` (default `0.0.0.0:7998`).

### Inbound adapter: `infrastructure/inbound/http/fastapi.py`
`SessionFastAPI` defines the session routes and `GET /health`, wraps every result in `StandardResponse` and calls the `SessionInboundPort`. `/session/message` runs the (synchronous) flow in a worker thread so the service stays responsive.

### Application

- `application/inbound/ports/`: interfaces the HTTP layer and services implement (`SessionInboundPort`, `MessageInboundPort`).
- `application/inbound/dto/`: request and response models.
- `application/outbound/ports/llm_ports.py`: `LLMOutboundPort`, the only thing the services know about the LLM (`ask(payload) -> Response`). Keep providers behind it.
- `application/service/session_service.py`: starts and ends sessions. `message_received` builds a `MessageFlowService` per message with the session's history, then remembers the exchange (last `AI_AGENT_HISTORY_TURNS` turns). `user_session.py` holds one session and its history.
- `application/service/message_flow_service.py`: thin adapter. `text()` runs the pipeline and keeps the per-message `metrics`.
- `application/orchestration/`: the agent itself (below).
- `application/system_prompts/advanced.py`: loads the prompt files (UTF-8, path resolved from the file). Every phase gets `0_generic_prompt.txt`, `capabilities.txt`, the date and then its own prompt (its `PROMPT_FILE`).

### Orchestration: `application/orchestration/`

Five folders, each with one job. The dependencies go one way (`tests/test_orchestration_layout.py` keeps it so): `flows` use everything below; `engine` never imports a flow; `phases` never imports the engine; `state` and `support` are the base.

```text
flows/     WHAT each agent is     one file per agent, plus the registry of the agents
phases/    the steps              one phase per file, constants first; the catalog; the shape of a phase
engine/    HOW any flow runs      knows no particular agent
state/     WHAT travels through a run
support/   shared helpers         model choice, metrics, failures, schemas, the action tree...
```

| File | Job |
|---|---|
| `flows/conversation_flow.py` | The conversation agent: triage, project manager, safety gate, action executor, draft writer, editor. Its fast path and the `robot_context` jump after triage. |
| `flows/motion_flow.py` | The movement agent: triage, motion planner, motion validator. |
| `flows/action_executor.py` | conversation-flow's step that runs the planned actions in dependency order (subactions and dependencies first), one LLM call each: the worker (phase 4) or the MCP operator (phase 5) by type, then the data engineer (phase 6) for MCP results. |
| `flows/fast_path.py` | Lets conversation-flow skip planning for a plain reply. |
| `flows/registry.py` | `FlowRegistry`: the flows this service hosts, by name. |
| `phases/{common,conversation_flow,motion_flow}/*.py` | **One phase per file**, constants first (`PHASE_ID`, `STEP_NAME`, `MODEL_ENV_VAR`, `DEFAULT_MODEL`, `PROMPT_FILE`, `FORMAT_NAME`, `INTENT`, `SCHEMAS`). `common` holds what several flows share (triage, answer checker, clarification). |
| `phases/phase.py` | `PhaseSpec` / `ActionPhaseSpec` (prompt file, model, intent, schema, what the phase reads, how it writes back) and `Step`. |
| `phases/catalog.py` | Every phase of every flow, read from the constants at the top of its file (id, name, prompt, default model, env variable). |
| `engine/pipeline.py` | The orchestrator of any flow: runs its steps in order, follows its jumps and stops to ask the user when a step leaves the flow waiting. `Pipeline(..., flow=...)`, then `run(message, history, paused, robot_context)`. |
| `engine/flow.py` | `Flow` (name, steps, jump after a step, result, starting state) and `FlowContext`. |
| `engine/phase_runner.py` | The only place an LLM `Payload` is built and sent. Records token usage. |
| `engine/clarification.py` | Phase 99: turns the missing inputs into a question for the user. |
| `engine/answer_check.py` | Phase 9: when a run is waiting for the user, decides if the next message is the answer, a yes or no, not an answer, or a request to stop. |
| `state/flow_state.py` | `FlowState`: everything the phases read and write for one message (intent, user goal, actions, next step, safety, history). |
| `state/motion_state.py` | `MotionFlowState`: `FlowState` plus motion-flow's movements and refusal. |
| `state/paused_run.py` | `PausedRun` (the saved run) and `FlowResult` (the reply plus the run that still waits). |
| `support/model_selection.py` | Which model answers a phase: its default or `AI_AGENT_MODEL_PHASE_<n>`. |
| `support/metrics.py` | `SessionMetrics`: tokens per phase and per model. |
| `support/failure.py` | `AgentFailure`, the attempts setting, and the apology that says what happened and why. |
| `support/schemas.py` | Loads the response JSON Schemas (cached, independent of the working directory). |
| `support/action_tree.py` | Helpers to look inside the action tree (subactions, execution order). |
| `support/mcp_servers.py` | How MCP servers are shown to the planner (name and tools, no connection settings). |
| `support/clock.py` | The current date and time shown to every phase. |

Adding a phase means its file, one line in `phases/catalog.py` and a step in its flow. Adding an agent means a file in `flows/` and one line in `flows/registry.py`; it gets its own routes and sessions.
### The pipeline

| Phase | Role | Model (default) | What it does |
|---|---|---|---|
| 1 | Triage specialist | `gpt-4.1-mini` | Classifies intent, extracts `user_goal`, `task_category`, first `next_step`. Sees the earlier turns of the session. The flow pauses here if it needs the user. |
| 2 | Project manager | `gpt-4.1` | Splits the goal into a tree of `actions` and sets `next_step`. Gets the MCP server list and the history. |
| 3 | Safety and quality gatekeeper | `gpt-4.1` | Fills `safety_and_validation` and updates `next_step`. |
| 4 | Cognitive worker | `gpt-4.1` | Runs one non-MCP action, given the outputs of its subactions and dependencies. |
| 5 | MCP operator | `gpt-4.1` | Runs one `mcp_tool_call` action with the tools of the MCP servers. Tried twice. If safety requires confirmation, it is blocked instead. |
| 6 | Data engineer | `gpt-4.1` | Cleans the result of an MCP action (only those). |
| 7 | Draft writer | `gpt-4.1` | Writes a first user-facing answer into `user_goal`. |
| 8 | Editor in chief | `gpt-4.1` | Polishes it. The reply is `user_goal.expected_outcome`. |
| 99 | User clarification | `gpt-4.1` | Not in the chain. When `next_step.status` is `awaiting_user_input` or `awaiting_confirmation` after phase 1, 2 or 3, the flow stops and this call writes the question. The run is saved in the session. |
| 9 | Answer checker | `gpt-4.1-mini` | Not in the chain. Reads the next message of a session with a saved run: answer (the waiting step runs again with it and the flow continues), yes or no (confirmation), not an answer (a message asks again, the run keeps waiting), or stop (the run is forgotten). |

Phases 1 to 9 and 99 are conversation-flow's. motion-flow adds phase 20 (motion planner, `gpt-4.1`: which arm, how many degrees, which direction, as an ordered list; it asks the user when one is missing) and phase 21 (motion validator, **no LLM call**: valid arm and direction, degrees within limits, at most 10 movements and 1440 degrees in total, and one bad movement refuses the whole sequence).

A simple question therefore costs 5 to 6 sequential LLM calls, more with many actions (one per action, plus one per MCP result).

### Domain: `domain/`
Pure data, no file or network access. `entities/` holds `Action`, `Response`, `Payload` and token usage. `value_objects/` has one file per concept (intent, user_goal, task_category, next_step, safety_and_validation, constraints, mcp_routing...) and the model catalog (`model_catalog.py` lists the model ids, `model.py` has `SelectedModel`).

### Prompts and schemas: `prompts/`, `schema/`
`prompts/` (flat, `<id>_<name>.txt`) has the instructions of each phase; the phase file says which one it uses. `schema/response/advanced/` has the JSON Schemas passed as `response_format` (`basic/` holds the complexity schema and older files). **Prompts, schemas and `domain/` must stay in sync**: changing a field means editing all three.

### Outbound LLM adapter: `infrastructure/outbound/llm/`
One module per job: `vercel.py` (`VercelAIAdapter.ask`: one stateless call, messages in, `Response` out), `config.py` (`VercelAIConfig`, keys and URLs), `provider_models.py` (domain model to `ai_sdk` model; a table of OpenAI-compatible routes, add a provider by adding a row), `tools.py` (`resolve_tools`: turns the MCP server list of phase 5 into real tools), `response_mapper.py` (LLM JSON to `Response`, one function per section). Native OpenAI and Anthropic; every other provider goes through its OpenAI-compatible base URL. History is put in the message text by the phases, not sent as chat turns.

### Outbound MCP: `infrastructure/outbound/mcp/`
`config.py` reads `mcps/*.json`. `MCPClientManager` opens an SSE connection (forwarding the trace headers). `MCPToolCatalog` knows which tools each server offers and which server owns a tool (cached, 10 s timeout, unreachable servers offer no tools). `MCPToolExecutor` is what the LLM adapter calls: `list_tools` and `execute`. Only `type: sse` servers work. `fetch` and `filesystem` are stdio (Docker), so they are skipped with a warning and never offer tools.

### Tests: `tests/`
All run without keys, network or cost:
- `test_flow_golden.py` records every LLM call of the pipeline (model, prompts, messages, schema, sampling, tools) and compares it with `tests/golden/flow_golden.json`.
- `test_flow_objects.py` (with `flow_trace.py`) runs a message through the real steps of the pipeline and only coordinates them. It saves, to files and not to the console, one markdown file per LLM call (the request at the top, the full object of the flow after the data was loaded at the bottom) plus the problems found in each answer. `tests/manual/debug_flow.py` does the same with the real LLM (`--real`) and can run one step alone many times on the same saved input and compare the runs. `tests/manual/debug_break.py` stops in a debugger at the start of each step and where the response is allocated. See `docs/debugging_the_flow.md`.
- `test_agent_behavior.py` covers settings, providers, tools, HTTP, session memory, models per phase and prompts.
- `test_units.py` covers the small modules: response mapper, schemas, provider routes, action tree, user session.
- `test_mcp_sse_integration.py` runs a real local MCP server.
- `test_session_fastapi.py` and `test_tracing.py` cover the HTTP layer and tracing.

`tests/manual/` holds scripts that call real services (real LLM, real MCP servers). pytest does not collect them.

## Known problems and decisions

Fixed (details in `docs/refactor_plan.md`): `.env` loading and key names, Ollama `KeyError`, `async` routes blocking on the flow, missing `/health`, mocked MCP tools and the crash when phase 5 received server configs, no memory between messages, error text returned as the reply, hardcoded models, working-directory dependent paths, mojibake of the prompt header (prompts were read with the Windows code page), no `.env.example`, unpinned requirements, manual scripts collected by pytest.

Checked and not a bug: `AnthropicModel` in `ai_sdk` is an OpenAI-client provider with a `base_url`, so using it for GitHub Models is correct.

Still open:
1. **No real LLM call has been made since these changes.** Whether GitHub Models accepts the `json_schema` `response_format` sent by the adapter, and whether the model returns bare JSON without code fences, is unverified. Do one real call first (`tests/manual/full_flow_real_llm.py`; it costs money).
2. Fixed 2026-09-22 (unmeasured): 5 to 6 sequential LLM calls per message is a lot for a voice robot. `AI_AGENT_FAST_PATH_ENABLED` (default on) skips project manager, the safety gate and action execution for a message triage classifies as pure information/conversation (`intent.primary` in `information_request`/`clarification_request` **and** `task_category` `generation`/`low`; both are checked because `generation`/`low` alone also covers real multi-step writing tasks like "make a table of my family", which still need a plan) — see `application/orchestration/flows/fast_path.py`. This was designed from the pipeline's own structure, not from a real measured voice-loop latency (measured with scripted LLMs only), so the actual win is unverified; revisit the trigger condition once real numbers exist.
3. **stdio MCP servers** (`fetch`, `filesystem`) are not supported, but the project manager is still told they exist, so it may plan actions that cannot run. `filesystem.json` mounts a hardcoded folder.
4. `SessionService` still builds a `MessageFlowService` (and its pipeline) per message. It is cheap, but it is not "once".
5. Fixed 2026-09-22: the session API now answers through `contracts.api` (`ApiEnvelope`, `data` built from `contracts.api.microservices.ai_agent.session.*`), like every other OBLIVION service, and `GET /available` exists (checks that a provider key or `OLLAMA_URL` is configured; makes no LLM call, so it cannot confirm the key actually works).
6. Arm movements are motion-flow's job (an ordered list of `{arm, degrees, direction}`, `data.directives` on `/motion-flow/session/message`), exercised end to end in `tests/test_motion_flow.py` with a scripted LLM. It has never been tried against a real LLM (whether the planner reliably writes a correct list, for example "left 90 and then back", is unverified) or against real stepper hardware.

## Configuration

Copy `.env.example` to `.env` (never commit or share it). Variables:
- Provider keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY`, `GROQ_API_KEY`, `COHERE_API_KEY`, `GITHUB_PAT`.
- Base URLs: `GOOGLE_URL`, `MISTRAL_URL`, `GROQ_URL`, `COHERE_URL`, `GITHUB_URL`, `OLLAMA_URL`.
- Service: `AI_AGENT_HOST`, `AI_AGENT_PORT`, `AI_AGENT_RELOAD`, `AI_AGENT_HISTORY_TURNS`, `AI_AGENT_MAX_ATTEMPTS` (default 3: how many times a failed LLM call, an MCP tool or a `retry` answer is tried).
- Models: which LLM each step uses is chosen in `config/step_models.json` (a `profile` for all steps, or one model per step in `steps`; see `docs/gemini_models_per_step.md` for the Gemini models, their prices and how each should perform on each step). `AI_AGENT_MODEL_PHASE_<n>` wins over the file. An unknown step or model fails at the first message. `tests/manual/show_models.py` shows what each step uses now (`--step=<step>` lists every model for that step with its cost per call and rating, `--set=<step>=<model id>` chooses one, `--profile=<name>` changes every step).

## Run

```powershell
& windows\Scripts\python.exe composition_root\main.py
```

It works from any folder (it changes to the project root). Then open <http://127.0.0.1:7998/docs> or call `GET /health`.

Tests (no keys, no cost):

```powershell
& windows\Scripts\python.exe -m pytest tests
```

## Layout

```text
composition_root/   app wiring (main.py)
application/        ports, DTOs, services, orchestration (the agent), system prompts
domain/             entities and value objects
infrastructure/     FastAPI inbound adapter (routes + response envelope), LLM and MCP outbound adapters
prompts/            prompt chain (0 generic + phases 1..8)
schema/             JSON Schemas of the structured response
mcps/               MCP server configs
docs/               GitHub Models notes, model per phase, refactor plan
tests/              pytest tests; tests/manual has scripts that call real services
```
