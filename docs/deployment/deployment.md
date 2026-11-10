# Deployment

The service is delivered by **GitHub Actions to a K3s cluster** (Rancher) as a container image, the same way as `dynamics_microservice`, whose workflows this pipeline was adapted from ([ADR-017](../decisions/ADR-017-ci-cd-github-actions-and-kubernetes.md)). **Status (2026-11-10, branch `feature_deployment`): written and checked on paper, never run.** No workflow has run, no image has been built (the Docker daemon was not running when it was written) and the variables and secrets of [`.env.github`](../../.env.github) are not set in GitHub yet. What was checked: the YAML, JSON and Markdown pass their linters, and the application starts (7 profiles ready, `GET /health` 200) from only the folders the image copies, with the bundled `shared-logging` wheel. The sibling `deployment/` project that older notes mention (it regenerated settings files from `.env.example`) is not part of this repository and whether it is still used next to this pipeline is UNKNOWN here.

## Run it

```powershell
# from the ai-agent folder; the venv is `windows` (Python 3.14 on Windows; 3.12+ elsewhere, see requirements.txt)
copy .env.example .env          # fill in at least one provider key and its URL; never commit .env
& windows\Scripts\python.exe composition_root\main.py
```

- Entry point: `composition_root/main.py` (it changes to the project root, so it works from any folder).
- Bind: `HTTP_ADDR` (`host:port` or `:port`, default `:7998`: the name and the format `dynamics_microservice` reads; it replaced `AI_AGENT_HOST` and `AI_AGENT_PORT`, so an old `.env` that sets those is ignored).
- `AI_AGENT_RELOAD` defaults to `1` (uvicorn auto-reload, for development). Use `0` for a stable run; the image and the deploy set `0`.
- Check it with `GET /health`; open `/docs` for Swagger.

## Image

`Dockerfile`, two stages, built with `target: production`: `builder` installs `requirements.txt` (with the two wheels of `vendor/`) into `/opt/venv`; `production` is `python:<PYTHON_VERSION>-slim` (default `3.14`, the Python of the venv the pins were taken from) with that venv and only what the service reads: `application`, `composition_root`, `domain`, `infrastructure`, `config`, `flows`, `mcps`, `model_sets`, `profiles`, `prompts`, `schema` and `step_defs`. No tests, docs, scripts, `.env` or `.env.*` (`.dockerignore`). It runs as uid `65534` with `AI_AGENT_RELOAD=0` and no `.pyc` files (the root filesystem is read-only in the cluster), and starts `python composition_root/main.py`.

```bash
docker build --target production -t ai-agent .
docker run --rm -p 7998:7998 --env-file .env ai-agent      # the file is read at run time, it is not in the image
```

## CI/CD (GitHub Actions, `.github/`)

| Workflow | When | What it does |
|---|---|---|
| `verify-topic-branch.yml` | push to `feature_*` | secret scan and lint only (fast feedback) |
| `verify-pr.yml` | pull request to `main` or `feature` | secret scan, lint **and tests**: the merge gate (mark its jobs as required checks in branch protection) |
| `deploy-to-dev.yml` | push to `feature`, or by hand | build and push the image, deploy to namespace `development` |
| `deploy-to-prod.yml` | push to `main`, or by hand | the same for namespace `production`; a running production deploy is never cancelled |

Pushes that only touch `*.md` or `docs/**` run nothing. The two deploys call `~flow-deploy.yml`; verification calls `~flow-verify.yml`; each step is its own file (`~step-1-secrets`, `~step-2-lint`, `~step-3-test`, `~step-4-build`, `~step-6-deploy`, `~step-7-notify`; `~step-5-scan`, Trivy, is written and switched off).

- **Step 1** TruffleHog over the history. **Step 2** Super-Linter, one run per language: YAML, JSON, Markdown, Dockerfile, GitHub Actions. Python is not linted (the project has no linter configuration); `docs/models/` (generated) and `vendor/` are excluded and the Markdown layout rules are relaxed (`.github/linters/.markdown-lint.yml`). **Step 3** `pip install -r requirements.txt`, then `scripts/split_schemas.py`, `scripts/check_agent.py` and `pytest tests`: no key, no network, no cost.
- **Step 4** builds `Dockerfile` and pushes `ghcr.io/<owner>/<repo>:latest` and `:<8-character sha>`. **Step 6** applies the namespace, the image pull secret and the application Secret, then the Deployment and the Service, and waits for the rollout (`GET /health`).
- **The kill switch:** the repository **Variable `DEPLOY_ENABLED`**. When it is `false` (any case), `~flow-deploy.yml` skips build, deploy and notify, for the push triggers and for a manual run alike, and the run page says so. Unset or any other value deploys. Verification is not affected.
- **Where each setting comes from.** Every setting of the project is a repository Variable (plain settings and public base URLs) or Secret (keys and private hosts) with the same name as the variable the code reads, listed in [`.env.github`](../../.env.github); one that is empty or unset is not written and the default of the code applies. The deploy writes them to one Kubernetes Secret, `<PROJECTNAME>-secrets`, which the pod reads with `envFrom`. The URL of `dynamics_microservice` differs per environment: the secrets `DYNAMICS_MCP_URL_DEVELOPMENT` and `DYNAMICS_MCP_URL_PRODUCTION` are written, according to the environment, as `DYNAMICS_MCP_URL`. The workflow **computes** only `PROJECTNAME`, `APP_ENV` and `HTTP_ADDR`, and they win; `AI_AGENT_RELOAD=0` comes from the image. The deploy stops if no provider key is set. Unlike the Go service, ai-agent has no `JOB_DIR`.
- **Port.** One number: `30000` (development) or `31000` (production) plus the Variable `PORT_OFFSET`, used in `HTTP_ADDR`, `containerPort`, Service `port`, `targetPort` and `nodePort`. The Service is a `NodePort` (same reason as the Go service: nothing else exposes the node); another workload in the cluster can also reach it by its service name. It has no authentication ([security](../security/security.md)).
- **One replica**, because the sessions are in the memory of the process ([ADR-009](../decisions/ADR-009-sessions-in-process-memory.md)): a second pod would answer `SESSION_NOT_FOUND` for the sessions of the first. Requests `256Mi` and `100m`, limits `1Gi` and `1` CPU (not measured: adjust after the first run). Liveness and readiness probes are both `GET /health`: ai-agent has no `/ready`, and `/health` answers once the profiles are loaded and never calls an LLM.

To switch the deploy off or on, in GitHub: Settings > Secrets and variables > Actions > Variables > `DEPLOY_ENABLED` = `false` or `true`.

## What the process needs

| Need | Where it comes from |
|---|---|
| Provider keys and URLs | environment or `.env` (see [environment-variables](../configuration/environment-variables.md)) |
| Which model answers each step | the model sets of `model_sets/` (files read once at start; no environment variable) |
| Prompts and schemas | `prompts/`, `schema/response/` (files read at run time, committed) |
| MCP servers (optional) | `mcps/*.json`; `type: sse` and `type: streamable_http` work. `DYNAMICS_MCP_URL` is the full URL (with `/mcp`) of `dynamics_microservice`; unset, that server is skipped with a warning |
| `contracts` | the wheel in `vendor/` |
| `shared-logging` | the wheel in `vendor/` (`shared_logging-0.1.0-py3-none-any.whl`, from `../shared-logging`; the image and the CI have no sibling checkout) |

## Reaching `dynamics_microservice`

- Today the Go service is open and ai-agent reaches it by a **public IP and port over plain HTTP**, set only in `DYNAMICS_MCP_URL` (never in git). That is accepted for the first stage ([ADR-011](../decisions/ADR-011-mcp-streamable-http.md)).
- When ai-agent runs **inside the Kubernetes network** (a web chat as the client), the value becomes a cluster service name: change the variable, nothing else. That step is documented here, not built.
- The Go service is started with `MCP_EXPOSE_GENERIC_TOOLS=false` (the agent only needs the workflows; ai-agent also hides every tool outside `allowed_tools`) and with its own `MCP_ENVIRONMENT` and `MCP_COMPANY` (the sandbox): ai-agent never sends an environment or a company.
- Neither service authenticates yet; see [security](../security/security.md).
- A deployment with **no robot connected** (a web chat) never asks the `gesture` profile: the service adds no gesture to a reply any more (T-05.7), so there is no variable to turn off.
- Model: the profile `claude_sonnet` (one Claude Sonnet model on every step) needs `ANTHROPIC_API_KEY`; it is not the active profile until the maintainer sets `profile` after the first real run.

## State

Sessions are in process memory only. A restart loses every session; Brain handles it by opening a new session and resending the message once (`SESSION_NOT_FOUND`, see [api](../api/api.md)). With more than one instance a session is only known to the one that created it.

## Tests before a release

The Verify flow runs them on every pull request (Step 3 above); by hand:

```powershell
& windows\Scripts\python.exe -m pytest tests          # no keys, no network, no cost
& windows\Scripts\python.exe scripts\split_schemas.py # check the schema tree (--write to rebuild)
```

The cross-service e2e tests are in `../contracts/tests/e2e/`.
