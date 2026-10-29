# CLAUDE.md: ai-agent

Port **7998** (`AI_AGENT_PORT`). Python/FastAPI. The "mind" of OBLIVION: it receives what the user said and **decides what to do**.
Status: prototype. Read `README.md` first, then `docs/architecture/architecture.md` (how it works), `docs/rules/schemas-and-prompts.md`,
`docs/configuration/environment-variables.md` and `../CLAUDE.md` (workspace rules). Each doc says which parts are generated or historical (`docs/README.md`).

State (2026-10-27): the four-flow redesign and the expression flow are merged into `feature` (PR #3, `e41b8b8`). Working branch
`feature_dynamics_mcp`: epic T-01, the read-only Business Central tools of `dynamics_microservice` through MCP (T-01.2 to T-01.8 and T-01.10 to T-01.12
done on 2026-10-28; T-01.9, the first real run, is the maintainer's; `docs/tasks/README.md`, ADR-011). Tests (2026-10-28): 919 passed, 0 failed, with the real `shared-logging` put on `PYTHONPATH` (`../shared-logging` is not installed in the `windows` venv; nothing was installed); `scripts/split_schemas.py` ignores line endings, so a CRLF checkout passes. Real LLM runs since the redesign (2026-10-28): three messages on `gemini-3-flash-preview` (T-02.10; the active profile got Google 503s that day), and two runs on Claude (T-03.6: `claude_haiku`, `claude_mixed`)
and no real call to the Go service. Epic T-02 (model catalog refresh, ADR-012, `docs/proposals/PR-004-model-catalog-gemini-free-tier.md`): T-02.1, T-02.2 and T-02.4 to T-02.9 done on 2026-10-28; T-02.3 (ids with the real key) and T-02.10 (first real run) done on 2026-10-28 with the Anthropic models; what they left on Google (`gemini-3.8-flash` 503, paid-only ids unchecked, token numbers of `proven` not measured) is not scheduled. Epic T-03 (Claude as a provider, ADR-013, `docs/tasks/T-03_claude-provider/`): T-03.1 to T-03.5 done on 2026-10-28, T-03.6 (first real run on Claude) done twice: Haiku with one wrong reply, then Sonnet 5.5 on planner, writer and editor (`claude_mixed`) with all three right. Check `git status` before editing.

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
  its answer (speaks it, moves the arms). Brain makes **one call per utterance** (`../brain_microservice/CLAUDE.md`).
- **Four flows** in one service and one venv: `identification` (triage), `conversation` (draft writer, editor), `special` (project manager,
  safety gate, action executor, draft writer, editor) and `movement` (motion planner, motion validator). Every message goes through
  identification; `task_category.domain` then picks ONE flow in `flows/router.py` (`FLOW_BY_DOMAIN`): `communication` -> conversation,
  `movement` -> movement, anything else -> special.
- The flows never call each other; only the router hands the identification state to the next one (nothing is classified twice). A flow that
  asked the user a question is resumed by the next message (`PausedRun.flow`) without identifying it again.
- **Gestures** (`AI_AGENT_EXPRESSION`, default on): after the conversation or special flow has written its reply, the router runs the
  `expression` flow on it (`emotion_reader`, one cheap model call, then `gesture_builder`, plain code). The result is random arm
  movements shaped by the emotion (`domain/operations/gesture.py`), with `pause_seconds` between them, about as long as the speech, every
  arm back where it started; they go out as `directives` with `gesture: true`. The reply is never held back: if the expression flow fails
  or the validator refuses the gesture, the reply goes out without one. A movement the user asked for (movement flow) gets no gesture.
  Brain starts a gesture when the robot starts to speak.
- Reads Business Central data, **read-only**, from `dynamics_microservice` through MCP in the special flow (Streamable HTTP;
  `mcps/dynamics_microservice.json`, its URL in `DYNAMICS_MCP_URL`, only the tools of its `allowed_tools`; `docs/api/api.md` "Tools consumed", ADR-011).
  Never an environment or a company is sent. `mcps/aws_microservice.json` (SSE) is still used by nothing.

## API

`POST /session/{start,message,end}`, `GET /health`, `GET /available`, `/docs`. Envelope `action / status / status_code / message / data / timestamp`,
`data` built from `contracts.api.microservices.ai_agent.session.*` (`infrastructure/inbound/http/fastapi.py`).

- `/message` takes `session_id`, `message`, `speak_movements` (default true, Brain's setting) and answers `response` (what to say; always speakable,
  an apology on failure), `directives` (movements in order, only the movement flow; `degrees` is signed), `awaiting_user_input` and `flow`.
  `response` is empty only for a movement that goes ahead with `speak_movements` off; a refusal or a question is always said.
- Sessions are in-process memory only (`SessionService.sessions`), lost on restart. `error_code == "SESSION_NOT_FOUND"` means exactly that
  (start a new session and retry the message once); any other `error_code` is a real failure, not a reconnect signal.
- `/available` only checks that a provider key or `OLLAMA_URL` is configured; it never calls an LLM.

## Layout (details in `docs/architecture/architecture.md`)

- `composition_root/main.py` builds the app (run this one): `VercelAIAdapter` -> one `SessionService` -> `SessionFastAPI`. Each message builds a
  `MessageFlowService` with an `AgentRouter`.
- `application/orchestration/` in five folders; **dependencies go one way** (`tests/test_orchestration_layout.py`): `flows` use everything below,
  `engine` never imports a flow, `phases` never import the engine, `state` and `support` are the base.
  - `flows/`: one file per flow, `router.py`, `registry.py`, `action_executor.py` (the special flow's step for phases 4-6).
  - `phases/`: one phase per file in `identification/`, `common/` (draft writer, editor, answer checker, clarification), `special/`, `movement/`.
    Every phase file declares its constants at the top (`PHASE_ID`, `STEP_NAME`, `MODEL_ENV_VAR`, `DEFAULT_MODEL`, `PROMPT_FILE`, `FORMAT_NAME`,
    `INTENT`, `SCHEMAS`); `catalog.py` reads them (`tests/test_phase_structure.py` enforces it). The motion validator is plain code (no LLM); its limits
    are constants at its top.
  - `engine/`: `pipeline.py`, `flow.py`, `phase_runner.py` (the only place an LLM payload is built), `clarification.py` (phase 99), `answer_check.py` (phase 9).
  - `state/`: `flow_state.py`, `motion_state.py`, `paused_run.py` (`PausedRun`, `FlowResult`). `support/`: model selection, metrics, failures, schemas, action tree.
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
- Do not hand-edit generated files: the schema tree, `docs/models/gemini_models_per_step.md`, `docs/models/models_per_step_budget.md`, `docs/models/cost_of_a_full_plan.md`.

## Config (details in `docs/configuration/environment-variables.md`)

- Models per step: `AI_AGENT_MODEL_PHASE_<n>` > `config/step_models.json` `steps` > the active profile > the code default (Google free-tier models: `gemini-3.1-flash-lite` for triage, data engineer, answer checker, clarification and emotion reader,
  `gemini-3.6-flash` for the rest (`gemini-3.8-flash` answered 503 "high demand" on 2026-10-28); the active profile `proven`, every step on `gemini-3.1-flash-lite`, wins over them, ADR-012). Prices and budget: `config/{gemini_models,other_models,budget,measured_runs}.json`.
- **Google free tier** (the default models): Google uses free-tier content to improve its products and does not publish its rate limits (measured 2026-10-28: `gemini-3.6-flash` about 7 calls in 30 s, then 429; `gemini-3.1-flash-lite` 10 of 10 in a row; and a **daily cap of 20 requests per model**, seen on `gemini-3-flash-preview`, about 2 to 5 messages a day); with a billed key the big plan costs about 175 EUR per 1,000 messages at paid prices (budget 50 EUR). `GITHUB_PAT` and `GITHUB_URL` are gone (GitHub Models is retired).
- **Claude** (profiles `claude_haiku`, `claude_mixed`, `claude_sonnet`; `ANTHROPIC_API_KEY`): through Anthropic's OpenAI-compatible endpoint with a strict, sanitized schema per call (`infrastructure/outbound/llm/anthropic_schema.py`, ADR-013): an action nests at most 3 levels and the endpoint hides Claude's thinking. Run twice on 2026-10-28 (`claude_haiku`, `claude_mixed`: the second with Sonnet 5.5 on planner, writer and editor, all right).
- `AI_AGENT_PARALLEL_ACTIONS` (default 1), `AI_AGENT_MAX_ATTEMPTS` (3), `AI_AGENT_HISTORY_TURNS` (6), `AI_AGENT_RELOAD` (defaults to `1`; `0` for a stable run).
- MCP: `DYNAMICS_MCP_URL` (unset: that server is skipped), `AI_AGENT_MCP_CALL_TIMEOUT_SECONDS` (30), `AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE` (5, `0` = no limit),
  `AI_AGENT_CHECK_MCP_<NAME>=1` (optional check, log only). The tool calls of a message may wait 60 s in total (a constant).
- Removed: `AI_AGENT_FAST_PATH_ENABLED` (the domain decides the flow now).
- **Langfuse** (when its keys are set) receives the user's text and the prompts and answers of every call, not only metadata; it never breaks a call.

## Commands

```powershell
& windows\Scripts\python.exe composition_root\main.py          # run from the ai-agent folder
& windows\Scripts\python.exe -m pytest tests                   # about 640 tests, no keys, no cost
& windows\Scripts\python.exe scripts\split_schemas.py          # check the schema tree (--write to rebuild it)
```

`tests/` is all mock-based and runs without the config file (`tests/conftest.py`). `tests/output/` holds generated reports of manual runs, not
documentation. `tests/manual/` scripts call real LLMs and MCP servers, are not collected by pytest, were not re-run after the redesign, and cost
money: ask first. The cross-service e2e tests are in `../contracts/tests/e2e/`.
