# ai-agent

The "mind" of OBLIVION. It receives what the user said (text), **decides**, and returns what to say, which arm movements to
run and whether it is waiting for an answer. It **never controls hardware**: `brain_microservice` calls it once per utterance
and acts on the answer (speaks it, moves the arms through the stepper).

- Port `7998` (`AI_AGENT_PORT`). Python, FastAPI, hexagonal layout, LLM access through `ai_sdk`, MCP client.
- Logging and tracing: `shared-logging`. Contracts: the bundled `contracts` wheel (`vendor/`, version in `requirements.txt`).
- Status: **prototype**. Everything is tested with scripted LLMs; nothing has run against a real LLM since the four-flow
  redesign of 2026-10-05 (see [Known problems](#known-problems-and-decisions)).

## How it works

Every message goes through the **identification** flow (triage: what is this?). The `task_category.domain` it finds then
picks **one** flow that answers:

```text
POST /session/message
        |
   identification            1 triage                       classifies; asks the user if it cannot
        |
        +-- communication --> conversation    7 draft writer -> 8 editor                               a plain reply
        +-- movement ------->  movement       20 motion planner -> 21 motion validator (code)          movements + a spoken line
        +-- anything else --> special         2 project manager -> 3 safety gate -> 4/5/6 action        a task: plan, check,
                                              executor -> 7 draft writer -> 8 editor                    execute, write
```

- The flows never call each other. `AgentRouter` (`application/orchestration/flows/router.py`) hands the identification
  state to the chosen flow, so nothing is classified twice.
- A flow that asks the user a question is **resumed by the next message** (the answer), without identifying it again.
- A greeting costs 3 LLM calls, a movement 2, a task 5 or more (one per action, plus one per tool result).
- Only the movement flow returns movements. Whether a movement that goes ahead is announced out loud is Brain's setting,
  sent with every message as `speak_movements` (a refusal or a question is always said).

The full explanation (folders, phases, engine, state, domain, extension recipes) is in
[`docs/guides/architecture.md`](docs/guides/architecture.md).

## Quick start

```powershell
# from the ai-agent folder; the venv is `windows` (Python 3.14 on Windows; 3.12+ elsewhere, see requirements.txt)
copy .env.example .env                  # fill in at least one provider key and its URL; never commit .env
& windows\Scripts\python.exe composition_root\main.py
```

Then open `http://<host>:7998/docs` or call `GET /health`. It works from any folder (it changes to the project root).
`AI_AGENT_RELOAD` defaults to `1` (auto-reload); set `0` for a stable run. Which model answers each step is chosen in
`config/step_models.json` (see [`docs/guides/configuration.md`](docs/guides/configuration.md)).

```powershell
& windows\Scripts\python.exe -m pytest tests          # no keys, no network, no cost
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/session/start` | create a session (`username`, optional `email`, optional `session_name`) and get a `session_id` |
| POST | `/session/message` | send `session_id` + `message` (+ `speak_movements`, default `true`) and get the answer |
| POST | `/session/end` | end the session |
| GET | `/health` | liveness (calls no LLM) |
| GET | `/available` | whether a provider key (or `OLLAMA_URL`) is configured (calls no LLM) |
| GET | `/docs` | Swagger UI |

Every request carries a `user_id` (3 to 128 characters). Responses use the envelope
`action / status / status_code / message / data / timestamp`, with `data` built from `contracts.api`.

`/session/message` answers (`AIAgentMessageResponse`):

| Field | Meaning |
|---|---|
| `success` | false when the message could not be processed (unknown session, LLM failure) |
| `response` | what to say. **Always speakable**: an apology when `success` is false. Empty only for a movement that goes ahead with `speak_movements` off |
| `directives` | the movements to run, in order: `[{arm, degrees, direction}]`. `degrees` is signed (left 90 then left -90 returns the arm). Only the movement flow sets it |
| `awaiting_user_input` | true when `response` is a question: the next message of the session is its answer |
| `flow` | which flow answered: `identification` (only when triage itself asks), `conversation`, `special` or `movement` |
| `message`, `error_code` | the technical reason of a failure and a code (below) |

**Session lifecycle.** Sessions are held **in process memory only**: they are lost when ai-agent restarts, and nothing expires
them (they live until `/session/end`). Use one session per conversation, reused across many utterances, so the history
(`AI_AGENT_HISTORY_TURNS`) means something. `error_code = SESSION_NOT_FOUND` on `/session/message` or `/session/end` means
exactly "this session no longer exists here": open a new one and, for a message, resend it once. Any other `error_code`
(`CONNECTION`, `TIMEOUT`, `AUTH`, `UNKNOWN`...) is a real failure of that one message, not a reason to reconnect.

## Where things are

```text
composition_root/   app wiring (main.py)
application/        ports, DTOs, services, orchestration (flows, phases, engine, state, support), system prompts
domain/             entities/ and value_objects/, each grouped in llm_request / llm_response / movement
infrastructure/     FastAPI inbound adapter, LLM adapter (ai_sdk), MCP client, Langfuse reporter
prompts/            one prompt per phase (<id>_<name>.txt), the generic rules and capabilities.txt
schema/response/    JSON Schemas of the answers: general/ (text flows) and motion/ (movement flow)
config/             models per step, prices, budget
mcps/               MCP server configs
scripts/            split_schemas.py (builds the schema tree)
docs/               documentation (index: docs/README.md)
tests/              pytest (all mock-based); tests/manual has scripts that call real services and cost money
```

## Documentation

| Read | For |
|---|---|
| [`docs/guides/architecture.md`](docs/guides/architecture.md) | how everything works and how to extend it |
| [`docs/guides/schemas_and_prompts.md`](docs/guides/schemas_and_prompts.md) | the prompts, the schema trees and how to change an answer |
| [`docs/guides/configuration.md`](docs/guides/configuration.md) | every setting, models per step, MCP servers, retries, Langfuse |
| [`docs/guides/debugging_the_flow.md`](docs/guides/debugging_the_flow.md) | tracing and debugging a message step by step |
| [`docs/README.md`](docs/README.md) | the index of `docs/`, including the generated and the historical files |
| `CLAUDE.md` | the rules for working in this folder |

## Tests

All run without keys, network or cost (about 640 tests, 25 s).

| File | Covers |
|---|---|
| `test_router.py`, `test_flows.py`, `test_motion_flow.py` | the routing by domain, the four flows, the routes, the movement flow and its validator |
| `test_resume.py` | pausing to ask the user and resuming (answers, confirmations, stop) |
| `test_flow_golden.py` | every LLM call of the pipeline (model, prompts, messages, schema, sampling, tools) against `tests/golden/flow_golden.json` |
| `test_flow_objects.py` (with `flow_trace.py`) | the real steps traced to files; which step writes which field |
| `test_parallel_actions.py`, `test_failures.py` | the action executor and the apologies for each kind of failure |
| `test_schema_tree.py`, `test_phase_structure.py`, `test_orchestration_layout.py` | the structure: schema tree, one phase per file, one-way dependencies |
| `test_model_config.py`, `test_budget_table.py`, `test_cost_estimate.py`, `test_usage_report.py` | model choice, cost tables, Langfuse reporting |
| `test_agent_behavior.py`, `test_units.py`, `test_session_fastapi.py`, `test_tracing.py`, `test_mcp_*` | settings, providers, tools, the mapper, the HTTP layer, tracing, a real local MCP server |

`tests/manual/` scripts call real LLMs and MCP servers; pytest does not collect them. They were not re-run after the redesign.
The cross-service tests (a real ai-agent process, Brain's real composition root) are in `contracts/tests/e2e/` at the workspace root.

## Known problems and decisions

Open:

1. **No real LLM call since the four-flow redesign.** The only real run was `gemini-2.5-flash` on 2026-09-21, before the flows
   existed. The configured profile (`budget50_groq`) was never run as a combination, and GitHub Models, the code default, is retired.
   Do one real call first (`tests/manual/full_flow_real_llm.py`; it costs money).
2. **The routing is only as good as triage's `domain`.** Everything depends on triage separating `communication` from a task ("make a
   table of my family" must be `writing`, not `communication`) and recognising a movement. The prompt explains each value, but only a
   real model can prove it. A wrong domain sends the message to the wrong flow, and a message that mixes a reply and a movement
   goes to one flow only. The movement flow answers a non-movement message with the planner's honest line, never silence.
3. **stdio MCP servers** (`fetch`, `filesystem`) are not supported, but the project manager is still told they exist, so it may plan
   actions that cannot run. `mcps/aws_microservice.json` hardcodes `http://localhost:8080/mcp/sse` (the Go service is unused today).
4. **Langfuse receives the user's text and the prompts** (not only metadata) when its keys are set. Use a project you trust.
5. `SessionService` builds a `MessageFlowService` (a router and four pipelines) per message. It is cheap, but it is not "once".
6. `constraints`, `mcp_routing` and `missing_information` are in the schemas and the domain but no phase writes them; `next_step.retry_action_id`
   is read but nothing acts on it.
7. The movement flow was exercised only with scripted LLMs and fake hardware (never a real LLM or a real stepper).

Decisions worth knowing: Brain makes one call per utterance (it used to ask two flows in order); the fast-path heuristic and
`robot_context` were removed; the answer schemas are one file per node, generated from `full.schema.json`;
`value_objects` and `entities` are grouped by what uses them. History of how it got here: `docs/history/refactor_plan.md`,
`docs/history/flows_refactor_plan.md` and the orchestrator notes (all marked historical).
