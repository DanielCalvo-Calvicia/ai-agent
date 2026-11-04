# CLAUDE.md: ai-agent

Port **7998** (`AI_AGENT_PORT`). Python/FastAPI. The "mind" of OBLIVION: it receives what the user said and **decides what to do**.
Status: prototype. Read `README.md` first, then `docs/architecture/architecture.md` (how it works), `docs/rules/schemas-and-prompts.md`,
`docs/configuration/environment-variables.md` and `../CLAUDE.md` (workspace rules). Each doc says which parts are generated or historical (`docs/README.md`).

State (2026-10-30): the four-flow redesign and the expression flow are merged into `feature` (PR #3, `e41b8b8`). Working branch
`feature_dynamics_mcp`: epic T-01, the read-only Business Central tools of `dynamics_microservice` through MCP (T-01.2 to T-01.8 and T-01.10 to T-01.12
done on 2026-10-28; T-01.9, the first real run, ran on 2026-10-29 with the real service (findings in its notes); `docs/tasks/README.md`, ADR-011). Tests (2026-10-30): 996 passed, 0 failed, with the real `shared-logging` put on `PYTHONPATH` (`../shared-logging` is not installed in the `windows` venv; nothing was installed); `scripts/split_schemas.py` ignores line endings, so a CRLF checkout passes. Real LLM runs since the redesign (2026-10-28): three messages on `gemini-3-flash-preview` (T-02.10; the active profile got Google 503s that day), and two runs on Claude (T-03.6: `claude_haiku`, `claude_mixed`)
and the Go service was called for real once, on 2026-10-29 (T-01.9). Epic T-02 (model catalog refresh, ADR-012, `docs/proposals/PR-004-model-catalog-gemini-free-tier.md`): T-02.1, T-02.2 and T-02.4 to T-02.9 done on 2026-10-28; T-02.3 (ids with the real key) and T-02.10 (first real run) done on 2026-10-28 with the Anthropic models; what they left on Google (`gemini-3.8-flash` 503, paid-only ids unchecked, token numbers of `proven` not measured) is not scheduled. Epic T-03 (Claude as a provider, ADR-013, `docs/tasks/T-03_claude-provider/`): T-03.1 to T-03.5 done on 2026-10-28, T-03.6 (first real run on Claude) and T-03.7 (prices) done, the epic closed on 2026-10-30: Haiku gave one wrong greeting, then Sonnet 5.5 on planner, writer and editor (`claude_mixed`) and six more greetings on Haiku were right. Epic T-04 (fallback models after a lack of capacity, ADR-014) done on 2026-10-29. Epic T-05 (profiles, flows and steps as pluggable layers, PR-005, ADR-015) is in progress on `feature_reorganitzation`: T-05.1 to T-05.18 done on 2026-11-02, 2026-11-03 and 2026-11-04: epic T-05 is closed (T-05.11, the first real run of `special` on `claude_mixed` with the real Dynamics service, passed on 2026-11-03: 8 calls, 41,513 tokens; 1371 tests pass). Epic T-06 (redesign, `docs/tasks/T-06_redesign/`) is in progress (2026-11-04): T-06.1 done (the seven profiles stay as T-05 built them; no new step, the tool caller is `mcp_operator`) T-06.3 closed with no change, and T-06.2 done (13 messages with tickable points in `tests/manual/profile_messages.json`, `run_profile.py --label before|after`, `tests/manual/README.md`; mock only, no real run yet); the prompt review is in the notes of T-06.4, which is next. No prompt, flow or profile has changed yet. Check `git status` before editing.

## MANDATORY: every change updates the documentation

No change is finished until the documents that describe it are true again. Do it in the same piece of work.

| If you change... | Update, in the same change |
|---|---|
| A flow, a phase, a folder or a file name | [docs/architecture/architecture.md](docs/architecture/architecture.md), the layout of [README.md](README.md) |
| An environment variable, a default or a model | `.env.example`, [docs/configuration/environment-variables.md](docs/configuration/environment-variables.md), the tables of [README.md](README.md) |
| A route, a request or answer field, an `error_code` | [docs/api/api.md](docs/api/api.md), [docs/requirements/requirements.md](docs/requirements/requirements.md) |
| A prompt, a schema or a `domain/` object | [docs/rules/schemas-and-prompts.md](docs/rules/schemas-and-prompts.md) and the golden file (on purpose) |
| Logging, tracing, Langfuse, failures | [docs/operations/monitoring.md](docs/operations/monitoring.md) |
| Secrets, exposure, data sent to providers | [docs/security/security.md](docs/security/security.md) |
| How it runs | [docs/deployment/deployment.md](docs/deployment/deployment.md) |
| A requirement or a known gap | [docs/requirements/requirements.md](docs/requirements/requirements.md) |
| The state of a task, a new task, a dependency | the task file, the board in [docs/tasks/README.md](docs/tasks/README.md) section 5 and [docs/tasks/ORDER.md](docs/tasks/ORDER.md) |
| A decision | a new ADR in [docs/decisions/](docs/decisions/) (or a dated note on the one it changes) |

Use dated notes in history (ADRs, proposals); correct the text in documents that describe the present. Mark what is planned as planned. Never describe as working something that is not. The generated files in `docs/models/` are not edited by hand.

## Role

- Only decides and returns a structured answer. It **never controls hardware** and never calls stepper, TTS or speaker; **Brain** acts on
  its answer (speaks it, moves the arms). Brain makes **one call per utterance today** (`../brain_microservice/CLAUDE.md`): it sends no profile, so it gets `default`; the client is meant to chain profiles (ADR-015, Brain's change is the maintainer's, later).
- **Profiles, flows and steps** (PR-005, ADR-015; built in epic T-05, T-05.1 to T-05.18): a request runs **ONE profile**, and a profile
  is one flow (`profiles/<name>.json`): `identification` (the triage alone), `chat` (`conversation` flow: draft writer, editor), `special` and
  `dynamics` (triage, project manager, safety gate, action executor, draft writer, editor; `dynamics` with only the Dynamics tools), `default`
  (the `special` flow with no tools; what a request with no profile gets), `movement` (motion planner, motion validator) and `gesture` (emotion
  reader, gesture builder). **The service no longer routes**: the client (Brain) asks `identification`, reads the domain and asks the profile
  that answers, then `gesture` for the reply; asking `identification` and then `special` runs the triage twice and the service says nothing
  (PR-005 section 3.3). `engine/profile_runner.py` (`ProfileRunner`) runs one profile; `tests/brain_chain.py` is the tests' model of the client's chain.
  A request with no `profile` runs `default`, so **the robot has no movement and no gesture** until Brain chains the profiles
  (accepted, Q07-14); a request that names a profile (with its token) runs that one. A run that asked the user a question is resumed by the next message of the same profile (`PausedRun.flow`).
- **Gestures**: the `gesture` profile (`emotion_reader`, one cheap model call, then `gesture_builder`, plain code) turns the emotion of an exchange into random
  arm movements (`domain/operations/gesture.py`), with `pause_seconds` between them, about as long as the speech, every arm back where it started. The
  service does not add one to a reply any more (`AI_AGENT_EXPRESSION` is gone): Brain asks the profile with the reply. Brain starts a gesture when the robot starts to speak.

- Reads Business Central data, **read-only**, from `dynamics_microservice` through MCP in the special flow (Streamable HTTP;
  `mcps/dynamics_microservice.json`, its URL in `DYNAMICS_MCP_URL`, only the tools of its `allowed_tools`; `docs/api/api.md` "Tools consumed", ADR-011).
  Never an environment or a company is sent. `mcps/aws_microservice.json` (SSE) is still used by nothing.

## API

`POST /session/{start,message,end}`, `GET /health`, `GET /available`, `/docs`. Envelope `action / status / status_code / message / data / timestamp`,
`data` built from `contracts.api.microservices.ai_agent.session.*` (`infrastructure/inbound/http/fastapi.py`).

- `/message` takes `session_id`, `message`, `speak_movements` (default true, Brain's setting) and, optional since T-05.9, `profile`, `token`, `inputs`, `return`, `pause_id`, `client` (read from ai-agent's own
  request model until the `contracts` repository has them; `docs/api/api.md`), and answers `response` (what to say; always speakable,
  an apology on failure), `directives` (movements in order, only the movement flow; `degrees` is signed), `awaiting_user_input` and `flow`, plus `profile`, `output`, `pause_id`, `discarded_pause` when they apply. A body with none of the new fields gets today's answer and runs `default`.
  Errors: `INVALID_PROFILE` (one generic answer for an unknown profile and a wrong token), `MISSING_INPUT`, `INVALID_INPUT`, `PROFILE_MISMATCH`, `PAUSE_NOT_FOUND`.
  `response` is empty only for a movement that goes ahead with `speak_movements` off; a refusal or a question is always said.
- Sessions are in-process memory only (`SessionService.sessions`), lost on restart. `error_code == "SESSION_NOT_FOUND"` means exactly that
  (start a new session and retry the message once); any other `error_code` is a real failure, not a reconnect signal.
- `/available` only checks that a provider key or `OLLAMA_URL` is configured; it never calls an LLM.

## Layout (details in `docs/architecture/architecture.md`)

- `composition_root/main.py` builds the app (run this one): `VercelAIAdapter` -> one `SessionService` -> `SessionFastAPI`. Each message builds a
  `MessageFlowService` with a `ProfileRunner` (one profile per message).
- `application/steps/` and `application/engine/` (with `engine/state/` and `engine/support/`); **dependencies go one way**
  (`tests/test_orchestration_layout.py`): `engine` uses only the shared `steps` (never the steps of one flow), `steps` never import the engine
  (only its base, `engine/state` and `engine/support`), `state` and `support` are the base. `application/flows/` is gone (T-05.12): a flow is the file `flows/<name>.json`.
  - **Flows are JSON (T-05.12)**: `flows/{identification,conversation,special,movement,expression}.json` (the names of the old Python flows, so the `flow` field of an answer and the metrics do not change): an ordered list of steps with `pause_if` and `retry_on_status`, `on_pause`/`on_resume` (only a flow that can ask) and `result_from`. `engine/flow_file.py` builds the `Flow` of each file; `assemble()` checks them and keeps them in `Agent.flows`. The names a flow may use are written in Python: `steps/conditions.py`, `steps/hooks.py` (hooks, result builders, the state a flow starts with) and `steps/build.py` (the function of a step). The router is gone (T-05.7).
  - **Steps are JSON (T-05.16)**: every LLM step is a declaration `step_defs/<name>.json` (kind, labels, prompt file, default model, intent, format, answer pieces of `schema/response/`, `reads` and `writes` that are fields of `config/state_fields.json` only; `functions` name a function of `steps/functions.py` when the plain lists are not enough). `steps/declared.py` builds the `PhaseSpec` from it; `assemble()` checks it and the data flow of every profile; the prompt is read through the configuration source (`Agent.step_prompts`). Adding an LLM step = one JSON file and a prompt (`tests/test_step_declarations.py`).
  - `steps/` (was `phases/`): Python only for the code steps (`special/action_executor.py`, `movement/motion_validator.py`, `expression/gesture_builder.py`) and the two prompts the engine runs itself (`common/answer_checker.py`, `common/user_clarification.py`); `registry.py`, `catalog.py`, `phase.py`, `declared.py`, `functions.py`.
    A Python step file declares its constants at the top (`PHASE_ID`, `STEP_NAME`, `DEFAULT_MODEL`, `PROMPT_FILE`; the numbers are labels) and registers itself in `steps/registry.py`; an LLM step enters the registry from its declaration; `catalog.py` reads the registry (`tests/test_phase_structure.py` enforces both). The motion validator is plain code (no LLM); its limits
    are constants at its top.
  - `engine/`: `pipeline.py`, `flow.py`, `phase_runner.py` (the only place an LLM payload is built), `clarification.py` (phase 99), `answer_check.py` (phase 9), `config_snapshot.py` (the configuration read once), `flow_file.py`, `profile_runner.py`, `assemble.py` (builds the agent from it and refuses what cannot work; a profile with a problem is disabled and logged at start, `scripts/check_agent.py` and the tests stop on it; T-05.6). The fields a step may read and write are the catalog `config/state_fields.json` (a test keeps it equal to the state classes).
  - **Tools (T-05.13)**: a step may use the tools every level that is set allows (profile `tools`, `flows.<flow>.tools`, the flow file's `tools`, a step's `tools` in the flow file, `overrides.<step>.tools`); `ToolScope` (`outbound/ports/mcp_ports.py`) is built per step by `Pipeline`, the planner is shown only those tools and `MCPToolExecutor.execute(scope=)` refuses the others.
  - **Prompts per profile (T-05.14)**: `overrides.<step>.prompt_append` / `prompt_replace` (a file under `prompts/` or inline text) change a step's prompt for one profile (`PromptOverride`, applied in `PhaseRunner`); the generic rules stay in front, the schema is the step's. `special` and `dynamics` use it twice (T-06.4 changes 2 and 3): `overrides.draft_writer.prompt_append` is `prompts/profiles/tools/draft_writer.txt` (the writer's rules for a tool answer) and `overrides.project_manager.prompt_append` is `prompts/profiles/tools/project_manager.txt` (how the planner picks a tool and fills its parameters); `chat` and `default` do not carry them.
  - **Metrics (T-05.15)**: one record per LLM call with `profile`, `flow`, `step`, `model`, `client`, tokens, `cost_usd` and `profile_hash` (SHA-256 of the assembled profile without its token hash, `AssembledProfile.profile_hash`); an INFO line `LLM call`; Langfuse tags and metadata; `SessionMetrics.total_by(...)`. `data.reads` and `data_allowed` are reserved: nothing reads them (a test).
  - `engine/state/`: `flow_state.py`, `motion_state.py`, `paused_run.py` (`PausedRun`, `FlowResult`). `engine/support/`: model selection, metrics, failures, schemas, action tree.
  - At the root (PR-005 section 8, each with a README): `profiles/` (the seven profiles; `_unverified/` holds the ten generic ones, not loaded) and `model_sets/` are filled; `flows/` holds the five flow files; `step_defs/` holds the 13 declarations; `prompts/profiles/` holds `tools/draft_writer.txt` and `tools/project_manager.txt` (shared by `special` and `dynamics`).
- `domain/`: `entities/` and `value_objects/`, each with `llm_request/`, `llm_response/` and `movement/`. Pure data, one file per concept.
- `infrastructure/`: inbound HTTP, outbound `llm/` (`vercel.py`, `provider_models.py`, `response_mapper.py`, `tools.py`), `mcp/`, `usage/` (Langfuse).
- `prompts/<id>_<name>.txt` (flat) plus `0_generic_prompt.txt` and `capabilities.txt`; which phase uses which is its `PROMPT_FILE`.
- `schema/response/general/` and `schema/response/motion/`: **`full.schema.json` is the one file you edit**; every other file is generated by
  `scripts/split_schemas.py --write` (without the flag it only checks), and `tests/test_schema_tree.py` fails on drift. The files the phases load
  must keep their content (`test_flow_golden.py`).
- **Keep prompts, schemas and `domain/` in sync** (`docs/rules/schemas-and-prompts.md`, section 4).

## Rules

- `.env` holds many provider keys. Never read the values out, print them or copy them; use variable names only.
- Uses `shared_logging` (`init_logging("ai-agent")`, `TracingMiddleware`, `-e ../shared-logging`) and the bundled `contracts` wheel in `vendor/`
  (refresh with `contracts/scripts/bundle.py`; the version is in `requirements.txt`).
- Keep the LLM adapter behind `LLMOutboundPort` so providers stay swappable.
- A change to a prompt, schema, model or message format changes the golden file: read the diff first, then regenerate on purpose (`UPDATE_GOLDEN=1`).
- **No log line, metric or span may hold a tool argument or a tool answer** (name, outcome, duration, tries only). The libraries under the MCP client are kept at WARNING for that (`quiet_client_libraries()`).
- Do not hand-edit generated files: the schema tree, `docs/models/gemini_models_per_step.md`, `docs/models/models_per_step_budget.md`, `docs/models/cost_of_a_full_plan.md`, `docs/models/profiles.md` (`scripts/model_tables.py`).

## Config (details in `docs/configuration/environment-variables.md`)

- Models per step: an ordered list in a model set (`model_sets/<name>.json`) or a profile; the first answers, the next ones are the fallback after a lack of capacity (ADR-014, T-05.5). The most specific value wins: `flows.<flow>.steps.<step>`, `overrides.<step>`, `flows.<flow>`, `models`, then the code default (Google free-tier models: `gemini-3.1-flash-lite` for triage, data engineer, answer checker, clarification and emotion reader,
  `gemini-3.6-flash` for the rest (`gemini-3.8-flash` answered 503 "high demand" on 2026-10-28). The profiles choose their model set: `proven` (every step on `gemini-3.1-flash-lite` with two fallbacks, ADR-012) for `default`, `identification`, `movement` and `gesture`, `claude_haiku` for `chat`, `claude_mixed` for `special` and `dynamics`. **No environment variable chooses a model any more** (`AI_AGENT_MODEL_PHASE_<n>`, `AI_AGENT_MODELS_FILE` and `AI_AGENT_FALLBACK_MODELS` are gone, `config/step_models.json` too). Prices and budget: `config/{gemini_models,other_models,budget,measured_runs}.json`.
- **Google free tier** (the default models): Google uses free-tier content to improve its products and does not publish its rate limits (measured 2026-10-28: `gemini-3.6-flash` about 7 calls in 30 s, then 429; `gemini-3.1-flash-lite` 10 of 10 in a row; and a **daily cap of 20 requests per model**, seen on `gemini-3-flash-preview`, about 2 to 5 messages a day); with a billed key the big plan costs about 175 EUR per 1,000 messages at paid prices (budget 50 EUR). `GITHUB_PAT` and `GITHUB_URL` are gone (GitHub Models is retired).
- **Claude** (model sets `claude_haiku`, `claude_mixed`, `claude_sonnet`; `ANTHROPIC_API_KEY`): through Anthropic's OpenAI-compatible endpoint with a strict, sanitized schema per call (`infrastructure/outbound/llm/anthropic_schema.py`, ADR-013): an action nests at most 3 levels and the endpoint hides Claude's thinking. Run twice on 2026-10-28 (`claude_haiku`, `claude_mixed`: the second with Sonnet 5.5 on planner, writer and editor, all right).
- `AI_AGENT_RETRY_WAIT_SECONDS` (1) and the rest of the ordered list of a step: a model out of capacity is waited for, then replaced by the next one of its list (ADR-014); the Claude model sets are one-item lists on purpose.
- `AI_AGENT_PARALLEL_ACTIONS` (default 1), `AI_AGENT_MAX_ATTEMPTS` (3), `AI_AGENT_HISTORY_TURNS` (6), `AI_AGENT_RELOAD` (defaults to `1`; `0` for a stable run).
- MCP: `DYNAMICS_MCP_URL` (unset: that server is skipped), `AI_AGENT_MCP_CALL_TIMEOUT_SECONDS` (30), `AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE` (5, `0` = no limit),
  `AI_AGENT_CHECK_MCP_<NAME>=1` (optional check, log only). The tool calls of a message may wait 60 s in total (a constant).
- Removed: `AI_AGENT_FAST_PATH_ENABLED` (the client reads the domain of `identification` and asks the profile that answers).
- **Langfuse** (when its keys are set) receives the user's text and the prompts and answers of every call, not only metadata; it never breaks a call.

## Commands

```powershell
& windows\Scripts\python.exe composition_root\main.py          # run from the ai-agent folder
& windows\Scripts\python.exe -m pytest tests                   # about 640 tests, no keys, no cost
& windows\Scripts\python.exe scripts\split_schemas.py          # check the schema tree (--write to rebuild it)
& windows\Scripts\python.exe scripts\check_agent.py            # assemble every profile, flow, step and model set; strict, files only (T-05.6)
& windows\Scripts\python.exe scripts\check_agent.py --explain special   # one profile in full: steps, models, tools, prompts, hash, cost of a full plan (T-05.17)
& windows\Scripts\python.exe scripts\model_tables.py --profiles   # docs/models/profiles.md, one table per profile (also --write, --budget, --step=<step>)
& windows\Scripts\python.exe scripts\run_profile.py special       # the fixed messages on the REAL models: asks first, costs money; --mock for no cost
```

`tests/` is all mock-based and runs without the config file (`tests/conftest.py`). `tests/output/` holds generated reports of manual runs, not
documentation. `tests/manual/` scripts call real LLMs and MCP servers, are not collected by pytest, were not re-run after the redesign, and cost
money: ask first. The cross-service e2e tests are in `../contracts/tests/e2e/`.
