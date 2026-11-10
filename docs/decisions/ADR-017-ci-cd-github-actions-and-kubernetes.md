# ADR-017 — Delivery by GitHub Actions to K3s, as a container, with a kill switch

**Status:** Accepted for the first run (2026-11-10, branch `feature_deployment`). Written, **not yet run**. ADR-016 (the runtime folder layout) is independent of this one.

## Context

Until now ai-agent was started by hand (`composition_root/main.py`) and [deployment](../deployment/deployment.md) said the repository had no Dockerfile, manifests or workflow. `dynamics_microservice` (Go) already has a pipeline: verify on pull requests, build an image to GHCR, deploy to a K3s cluster managed with Rancher, one Kubernetes Secret per application built from GitHub Variables and Secrets. The owner asked for the same for ai-agent, with an internal GitHub variable that turns the deploy off, and for a check that the names of the environment variables fit.

## Decision

1. **The same shape as `dynamics_microservice`**: `verify-topic-branch`, `verify-pr`, `deploy-to-dev` (push to `feature`), `deploy-to-prod` (push to `main`), `~flow-*` and `~step-*` reusable workflows, the namespaces `development` and `production`, a NodePort Service whose port is `30000` or `31000` plus `PORT_OFFSET`, one Secret `<PROJECTNAME>-secrets` read with `envFrom`, and one repository Variable or Secret per setting. The `APP_CONFIG_*` blocks of the Go service are not used: ai-agent has no free-named settings, so every setting is listed by name in `.env.github`.
2. **Kill switch**: the repository Variable `DEPLOY_ENABLED`. `false` skips build, deploy and notify in `~flow-deploy.yml`, so it also stops a manual run. Unset or any other value deploys (the literal reading of the request; to make "unset" mean "off", change `!= 'false'` to `== 'true'` in that file).
3. **What changes for Python**: Step 3 runs `scripts/split_schemas.py`, `scripts/check_agent.py` and `pytest` instead of Go's vet and test; Step 2 drops Go and keeps YAML, JSON, Markdown, Dockerfile and GitHub Actions (Python is not linted: the project has no linter configuration and one with defaults would fail on correct code); the image is `python:<version>-slim` with a virtual environment, non-root, read-only root filesystem.
4. **The listen address was renamed to the Go service's name.** `AI_AGENT_HOST` and `AI_AGENT_PORT` are replaced by `HTTP_ADDR` (`host:port` or `:port`, default `:7998`, parsed by `infrastructure/inbound/http/address.py`): the pipeline computes one `HTTP_ADDR` from the port scheme, as it does for the Go service. The workflow also computes `PROJECTNAME` and `APP_ENV` (read by `shared-logging`). `AI_AGENT_RELOAD` has no Go counterpart and is not computed: the Dockerfile sets it to `0` (the code default `1` would start uvicorn's reloader in the cluster). `LOG_*` and `APP_ENV`, which the code reads through `shared-logging` but `.env.example` did not list, are now listed.
5. **`shared-logging` is bundled as a wheel in `vendor/`**, like `contracts`, because `-e ../shared-logging` needs a sibling checkout that neither the image build nor the CI runner has (and `shared-logging` is not in a repository of its own). The wheel is a snapshot of `../shared-logging` 0.1.0; refreshing it after a change there is manual.
5. **Every variable of the project is a Variable or a Secret**, with the name the code reads (keys and private hosts are Secrets), so a provider added later needs no workflow change. The URL of `dynamics_microservice` is the exception: it is one secret per environment, `DYNAMICS_MCP_URL_DEVELOPMENT` and `DYNAMICS_MCP_URL_PRODUCTION`, written as `DYNAMICS_MCP_URL`. The deploy stops when no provider key is set.
6. **One replica**, because the sessions are in process memory ([ADR-009](ADR-009-sessions-in-process-memory.md)).

## Consequences

- A merge to `feature` deploys to `development`, and a merge to `main` deploys to `production`, unless `DEPLOY_ENABLED` is `false`. Branch protection must require the jobs of `verify-pr` (set in GitHub, not in the repository).
- A change to `../shared-logging` does not reach the image until its wheel in `vendor/` is rebuilt; a stale wheel is silent.
- The image installs every package of `requirements.txt`, including the pinned ones that no code imports (`langchain*`, `pymongo`, `google-genai` and others) and `pytest`; trimming them is a separate change.
- `dynamics_microservice` has to be reachable from the pod: `DYNAMICS_MCP_URL` is a Secret per environment (a cluster service name such as `http://<its PROJECTNAME>.<namespace>.svc.cluster.local:<its port>/mcp` should work, not verified). Neither service authenticates ([security](../security/security.md)).
- Not verified at all: the pipeline itself, the image build, the memory and CPU requests, and that the Markdown and Dockerfile lint pass in Super-Linter. See known gap 7 of [requirements](../requirements/requirements.md).
