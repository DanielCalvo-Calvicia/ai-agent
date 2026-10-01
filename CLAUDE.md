# CLAUDE.md: ai-agent

Port **7998** (`AI_AGENT_PORT`; changed from 8000, which clashed with microphone). Python/FastAPI. The "mind" of OBLIVION: it receives what the user said and **decides what to do**. Status: prototype. See `README.md` and `../CLAUDE.md`.

Current state (2026-09-22): branch `feature_ai_claude`, last commit "Refactor the agent orchestrator, add per-step models, budget profiles and Langfuse cost tracking". 79 uncommitted files, about 70 of them `__pycache__/*.pyc` noise. Check `git status` before editing.

## Role

- Only decides and returns a structured response. It **never controls hardware** and never calls stepper, TTS or speaker. **Brain** acts on its answer (speak, move an arm).
- **Hosts several agents, called flows**, in one service and one venv. Today two: **`conversation-flow`** (writes the reply) and **`motion-flow`** (turns what the user said into an ordered list of arm movements). They never call each other: **Brain** asks motion-flow first, then conversation-flow with what motion-flow decided (`robot_context`). A new agent = a file in `orchestration/flows/`, its own phase files and one line in `flow_registry.py`.
- Brain calls it per utterance (see `../brain_microservice/CLAUDE.md`).
- May later fetch content from `aws_microservice` through MCP (`mcps/aws_microservice.json` → `/mcp/sse` on port 8080). Nothing uses this yet.

## API

Every flow has its own routes and its own sessions: `POST /conversation-flow/session/{start,message,end}` and `POST /motion-flow/session/{start,message,end}`, plus `GET /health`, `GET /available` and `/docs` once. The original `POST /session/{start,message,end}` stays as a deprecated alias of conversation-flow (same sessions) until nothing calls it. Responses use the standard envelope (`action / status / status_code / message / data / timestamp`).

- conversation-flow `/message` answers `data.response` (the reply). Its request may carry `robot_context` (`{directives: [{arm, degrees, direction}], rejected_reason}`): what motion-flow decided. With one the flow skips planning (triage, draft writer, editor) and the reply only says what the robot is doing, or why it cannot; it never says a movement is done and never pauses to ask about it.
- motion-flow `/message` answers `data.directives` (the movement sequence, in order; `degrees` is signed, so left 90 then left -90 returns the arm), `data.response` (a refusal to speak, or the question) and `data.awaiting_user_input` (true when `response` is a question: the flow is paused and the next message is its answer). Every message goes through it, not only movement requests; a message that asks for no movement comes back with no directives and an empty `response`.

Sessions are in-process memory only (`SessionService.sessions`), lost on restart. `data.error_code == "SESSION_NOT_FOUND"` on `/session/message` or `/session/end` means exactly that — the caller's move is to start a new session and (for a message) retry once — any other `error_code` is a real failure, not a reconnect signal. See README.md's "Session lifecycle" section.

## Layout

- `composition_root/main.py`: builds the app (run this one). Wiring: `VercelAIAdapter` (outbound LLM) → `SessionService` → `SessionFastAPI` (inbound).
- `application/`: inbound ports and DTOs, `service/` (`session_service` keeps per-session history, `message_flow_service` is a thin adapter), outbound `llm_ports`, `system_prompts/`.
- `application/orchestration/`: the agents and their engine, in five folders. **Dependencies go one way** (`tests/test_orchestration_layout.py`): `flows` use everything below, `engine` never imports a flow, `phases` never imports the engine, `state` and `support` are the base.
  - `flows/`: **what each agent is.** `conversation_flow.py` (triage, project manager, safety gate, action executor, draft writer, editor; its fast path and `robot_context` jumps after triage), `motion_flow.py` (triage, motion planner, motion validator), `action_executor.py` (conversation-flow's step that runs planned actions, phases 4-6), `fast_path.py` (`AI_AGENT_FAST_PATH_ENABLED`, default on: after triage, jump to `draft_writer` for a plain reply; the module docstring says why `task_category` alone is not a safe signal) and `registry.py` (the flows this service hosts). A new agent = a file here + its phase files + one line in the registry.
  - `phases/`: **the steps, one phase per file**, in `common/` (triage, answer checker, user clarification: used by several flows), `conversation_flow/` and `motion_flow/`. Every phase file declares what it uses as constants at its top: `PHASE_ID`, `STEP_NAME`, `MODEL_ENV_VAR`, `DEFAULT_MODEL`, `PROMPT_FILE` (`prompts/<id>_<name>.txt`), `FORMAT_NAME`, `INTENT` and the schema files it reads (`SCHEMAS`). `catalog.py` reads them (the prompt loader, model selection and metrics take their tables from it), `phase.py` is the shape of a phase (`PhaseSpec`, `ActionPhaseSpec`, `Step`). `tests/test_phase_structure.py` enforces one phase per file, every constant, every file exists. A new phase = its file + one line in `catalog.py` + a step in its flow. motion-flow's validator (`phases/motion_flow/motion_validator.py`) is plain code, not an LLM call; its limits are constants at its top.
  - `engine/`: **how any flow runs.** `pipeline.py` (`Pipeline(..., flow=...)` runs the steps of a flow, follows its jumps, pauses to ask the user and resumes; it has no default flow), `flow.py` (the `Flow` dataclass: name, `build_steps`, `jump_after`, `build_result`, `new_state`), `phase_runner.py` (the only place an LLM payload is built), `clarification.py` (phase 99) and `answer_check.py` (phase 9).
  - `state/`: **what travels through a run.** `flow_state.py`, `motion_state.py` (adds motion-flow's fields), `paused_run.py` (`PausedRun`, `FlowResult`).
  - `support/`: shared helpers. `model_selection.py`, `metrics.py`, `failure.py`, `schemas.py`, `action_tree.py`, `mcp_servers.py`, `clock.py`.
  - conversation-flow no longer plans or parses movements (there is no `robot_action` any more): motion-flow does. Model steps: `motion_planner` (phase 20, `AI_AGENT_MODEL_PHASE_20`) can be set in `config/step_models.json` and in a profile like any other step; the cost and budget tables (`STEP_NAMES`) cover conversation-flow's steps only.
- `domain/`: entities and value objects, one file per concept. Pure data (JSON schemas are loaded by `application/orchestration/support/schemas.py`).
- `infrastructure/`: `inbound/http/` (`fastapi.py`, `responses.py`), `outbound/llm/` (`vercel.py`, `config.py`, `provider_models.py`, `tools.py`, `response_mapper.py`), `outbound/mcp/`, `outbound/usage/langfuse.py`.
- `prompts/<id>_<name>.txt` (flat): `0_generic_prompt.txt` (rules of every phase), `capabilities.txt` (what the robot can and cannot do), `1..9_*` the conversation chain (triage → PM → safety gatekeeper → worker → MCP operator → data engineer → writer → editor, answer checker) and `20_motion_planner.txt`. Which phase uses which prompt is the `PROMPT_FILE` constant of the phase file.
- `schema/response/advanced/`: JSON Schemas of the structured LLM response. **Keep prompts, schemas and `domain/` in sync.**
- `mcps/*.json`: MCP server configs (`aws_microservice` SSE, `fetch` via Docker, `filesystem`).

## Rules

- `.env` holds many provider keys (OpenAI, Anthropic, Google, Mistral, Groq, Cohere, GitHub PAT). Never read the values out, print them or copy them. Use variable names only.
- Uses `shared_logging` (`init_logging("ai-agent")`, `TracingMiddleware`, `-e ../shared-logging`). Since 2026-09-22 it also uses `contracts` (`./vendor/contracts_microservice-0.7.1-py3-none-any.whl`, bundled by `contracts/scripts/bundle.py` like the other services): `/health`, `/available`, `/session/start`, `/session/end` and `/session/message` answer with `contracts.api.common.envelope.ApiEnvelope`, `data` built from `contracts.api.microservices.ai_agent.session.*` / `contracts.api.microservices.common` (see `infrastructure/inbound/http/fastapi.py`). `/available` (`LLMOutboundPort.is_available()`, implemented on `VercelAIAdapter`) only checks that a provider key or `OLLAMA_URL` is configured; it never calls an LLM, so it cannot tell whether the configured provider is actually reachable or the key is valid.
- Keep the LLM adapter behind `LLMOutboundPort` so providers stay swappable.

## Config

- Models per step: `config/step_models.json` (profile, per-step `steps`); `AI_AGENT_MODEL_PHASE_<n>` wins over it.
- Prices and plans: `config/{gemini_models,other_models,budget,measured_runs}.json`. `docs/gemini_models_per_step.md` and `docs/models_per_step_budget.md` are generated from them (`tests/manual/show_models.py --write` / `--budget`).
- `AI_AGENT_PARALLEL_ACTIONS=<n>` runs independent actions of a plan together (default 1; tool calls stay sequential).
- `AI_AGENT_FAST_PATH_ENABLED=0` disables the fast path (see `application/orchestration/fast_path.py`); default is on.
- Cost tracking: sends metadata only to Langfuse when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set, via `UsageReporterPort`/`SessionMetrics`. It never breaks a call.

## Commands

```powershell
& windows\Scripts\python.exe composition_root\main.py    # run from the ai-agent folder
& windows\Scripts\python.exe -m pytest tests
```

`tests/` is all mock-based (no keys, no cost) and runs without the config file (`tests/conftest.py`). `tests/test_flow_golden.py` records every LLM call and compares with `tests/golden/flow_golden.json`: a refactor must keep it green. Regenerate it (`UPDATE_GOLDEN=1`) only for a deliberate change to prompts, models, schemas or message formats. `tests/manual/` scripts call real LLMs and MCP servers, are not collected by pytest, and cost money: ask first.
