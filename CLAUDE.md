# CLAUDE.md: ai-agent

Port **7998** (changed from 8000, which clashed with microphone). Python/FastAPI. The "mind" of OBLIVION: it receives what the user said and **decides what to do**. Status: prototype. See `README.md` and `../CLAUDE.md`.

## Role

- Only decides and returns a structured response. It **never controls hardware** and never calls stepper, TTS or speaker. **Brain** acts on its answer (speak, move an arm).
- Not connected to Brain yet. The plan is Brain → `POST /session/message` between STT and TTS.
- May later fetch content from `aws_microservice` through MCP (`mcps/aws_microservice.json` → `http://localhost:8080/mcp/sse`). Nothing uses this yet.

## API

`POST /session/start`, `POST /session/message`, `POST /session/end`, `GET /health`, plus `/docs`. Responses use the standard envelope (`action / status / status_code / message / data / timestamp`).

## Layout

- `composition_root/main.py`: builds the app (run this one). Wiring: `VercelAIAdapter` (outbound LLM) → `SessionService` → `SessionFastAPI` (inbound).
- `application/`: inbound ports and DTOs, `service/` (`session_service` keeps per-session history, `message_flow_service` is a thin adapter), outbound `llm_ports`, `system_prompts/`.
- `application/orchestration/`: the agent. `pipeline.py` lists the steps in order, `phase_runner.py` is the only place an LLM payload is built, `action_walker.py` runs phases 4-6 per action, `clarification.py` is phase 99, `phases/` has one `PhaseSpec` per whole-response phase. A new phase = one spec file + one line in `build_steps`.
- `domain/`: entities and value objects. One file per concept. Pure data: no file or network access (JSON schemas are loaded by `application/orchestration/schemas.py`).
- `infrastructure/`: `inbound/http/` (`fastapi.py` routes, `responses.py` envelope), `outbound/llm/` (one module per job: `vercel.py` adapter, `config.py`, `provider_models.py` route table, `tools.py`, `response_mapper.py`), `outbound/mcp/` (`client_manager`, `tool_catalog`, `tool_executor`, `config`).
- `prompts/advanced/0..8_*.txt`: the multi-role prompt chain (triage → PM → safety gatekeeper → worker → MCP operator → data engineer → writer → editor).
- `schema/response/advanced/`: JSON Schemas for the structured LLM response. **Keep prompts, schemas and `domain/` in sync.** Changing one means changing the others.
- `mcps/*.json`: MCP server configs (`aws_microservice` SSE, `fetch` via Docker, `filesystem`).
- `docs/`: notes on GitHub Models and the recommended model per phase.

## Rules

- `.env` holds many provider keys (OpenAI, Anthropic, Google, Mistral, Groq, Cohere, GitHub PAT). Never read the values out, print them or copy them anywhere. Use variable names only.
- Uses `shared_logging` (`init_logging("ai-agent")` is already called). It does not use `contracts` yet. Its session API is a candidate for `contracts.api`, but do not change that unasked.
- Keep the LLM adapter behind `LLMOutboundPort` so providers stay swappable.

## Commands

```powershell
& windows\Scripts\python.exe composition_root\main.py    # run from the ai-agent folder
& windows\Scripts\python.exe -m pytest tests
```

`tests/` is all mock-based (no keys, no cost). `tests/test_flow_golden.py` is a characterization test: it records every LLM call of the pipeline and compares with `tests/golden/flow_golden.json`. A refactor must keep it green. Regenerate the golden file (`UPDATE_GOLDEN=1`) only for a deliberate change to prompts, models, schemas or message formats. `tests/manual/` has scripts that call real services (real LLM, MCP servers) and are not collected by pytest. Real LLM calls cost money: ask first.

Settings come from `.env` (see `.env.example`), loaded by `main.py`. Models per step: `config/step_models.json` (profile, per-step `steps`), then `AI_AGENT_MODEL_PHASE_<n>` wins. Prices and ratings of the Gemini models: `config/gemini_models.json`, and `docs/gemini_models_per_step.md` is generated from it (`tests/manual/show_models.py --write`). Other providers: `config/other_models.json`; budget and plan sizes: `config/budget.json`; measured runs: `config/measured_runs.json`. `docs/models_per_step_budget.md` is generated from them (`tests/manual/show_models.py --budget`). The tests run without the config file (`tests/conftest.py`). Speed: `AI_AGENT_PARALLEL_ACTIONS=<n>` runs the independent actions of a plan at the same time (`action_executor._settle_all`; tool calls stay one by one; default 1). Cost tracking: `infrastructure/outbound/usage/langfuse.py` sends each LLM call (model, tokens with thinking, cost) to Langfuse when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set; it goes through `UsageReporterPort` and `SessionMetrics`, sends metadata only and never breaks a call.
