# CLAUDE.md: ai-agent

Port **7998** (`AI_AGENT_PORT`; changed from 8000, which clashed with microphone). Python/FastAPI. The "mind" of OBLIVION: it receives what the user said and **decides what to do**. Status: prototype. See `README.md` and `../CLAUDE.md`.

Current state (2026-09-22): branch `feature_ai_claude`, last commit "Refactor the agent orchestrator, add per-step models, budget profiles and Langfuse cost tracking". 79 uncommitted files, about 70 of them `__pycache__/*.pyc` noise. Check `git status` before editing.

## Role

- Only decides and returns a structured response. It **never controls hardware** and never calls stepper, TTS or speaker. **Brain** acts on its answer (speak, move an arm).
- Not connected to Brain yet. The plan is Brain → `POST /session/message` between STT and TTS.
- May later fetch content from `aws_microservice` through MCP (`mcps/aws_microservice.json` → `/mcp/sse` on port 8080). Nothing uses this yet.

## API

`POST /session/start`, `POST /session/message`, `POST /session/end`, `GET /health`, `GET /available`, plus `/docs`. Responses use the standard envelope (`action / status / status_code / message / data / timestamp`).

Sessions are in-process memory only (`SessionService.sessions`), lost on restart. `data.error_code == "SESSION_NOT_FOUND"` on `/session/message` or `/session/end` means exactly that — the caller's move is to start a new session and (for a message) retry once — any other `error_code` is a real failure, not a reconnect signal. See README.md's "Session lifecycle" section.

## Layout

- `composition_root/main.py`: builds the app (run this one). Wiring: `VercelAIAdapter` (outbound LLM) → `SessionService` → `SessionFastAPI` (inbound).
- `application/`: inbound ports and DTOs, `service/` (`session_service` keeps per-session history, `message_flow_service` is a thin adapter), outbound `llm_ports`, `system_prompts/`.
- `application/orchestration/`: the agent. `pipeline.py` lists the steps in order, `phase_runner.py` is the only place an LLM payload is built, `action_walker.py` runs phases 4-6 per action, `action_executor.py` runs the actions, `clarification.py` is phase 99, `phases/` has one `PhaseSpec` per whole-response phase. A new phase = one spec file + one line in `build_steps`. `robot_directive.py` reads the finished action tree for a `robot_action`-typed action and turns its (deterministically formatted) output into a `RobotDirective` on `FlowResult` — the agent never moves anything itself, it only hands the request to Brain via `/session/message`'s `data.directive`. `fast_path.py` (`AI_AGENT_FAST_PATH_ENABLED`, default on): after triage, jumps straight to `draft_writer` (skipping `project_manager`/`safety_quality_gatekeeper`/`action_executor`) when `intent.primary` and `task_category` both say "plain information/conversation, not a task" — see the module docstring for why `task_category` alone (`generation`/`low`) is not a safe enough signal on its own.
- `domain/`: entities and value objects, one file per concept. Pure data (JSON schemas are loaded by `application/orchestration/schemas.py`).
- `infrastructure/`: `inbound/http/` (`fastapi.py`, `responses.py`), `outbound/llm/` (`vercel.py`, `config.py`, `provider_models.py`, `tools.py`, `response_mapper.py`), `outbound/mcp/`, `outbound/usage/langfuse.py`.
- `prompts/advanced/0..8_*.txt`: the multi-role prompt chain (triage → PM → safety gatekeeper → worker → MCP operator → data engineer → writer → editor).
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
