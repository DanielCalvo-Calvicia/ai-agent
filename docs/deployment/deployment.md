# Deployment

This repository has **no Dockerfile, no Kubernetes manifests and no CI workflow**. In the OBLIVION workspace the delivery is done by the sibling `deployment/` project, which regenerates its settings files from this service's `.env.example` (`deployment/scripts/env_inventory.py --write`). How and where it runs in production is outside this repository: UNKNOWN here.

## Run it

```powershell
# from the ai-agent folder; the venv is `windows` (Python 3.14 on Windows; 3.12+ elsewhere, see requirements.txt)
copy .env.example .env          # fill in at least one provider key and its URL; never commit .env
& windows\Scripts\python.exe composition_root\main.py
```

- Entry point: `composition_root/main.py` (it changes to the project root, so it works from any folder).
- Bind: `AI_AGENT_HOST` (default `0.0.0.0`) and `AI_AGENT_PORT` (default `7998`).
- `AI_AGENT_RELOAD` defaults to `1` (uvicorn auto-reload, for development). Use `0` for a stable run; the deploy tool sets `0`.
- Check it with `GET /health`; open `/docs` for Swagger.

## What the process needs

| Need | Where it comes from |
|---|---|
| Provider keys and URLs | environment or `.env` (see [environment-variables](../configuration/environment-variables.md)) |
| Which model answers each step | `config/step_models.json` or `AI_AGENT_MODEL_PHASE_<n>` |
| Prompts and schemas | `prompts/`, `schema/response/` (files read at run time, committed) |
| MCP servers (optional) | `mcps/*.json`; only `type: sse` works |
| `contracts` | the wheel in `vendor/` |
| `shared-logging` | `../shared-logging` (editable install) |

## State

Sessions are in process memory only. A restart loses every session; Brain handles it by opening a new session and resending the message once (`SESSION_NOT_FOUND`, see [api](../api/api.md)). With more than one instance a session is only known to the one that created it.

## Tests before a release

```powershell
& windows\Scripts\python.exe -m pytest tests          # no keys, no network, no cost
& windows\Scripts\python.exe scripts\split_schemas.py # check the schema tree (--write to rebuild)
```

The cross-service e2e tests are in `../contracts/tests/e2e/`.
