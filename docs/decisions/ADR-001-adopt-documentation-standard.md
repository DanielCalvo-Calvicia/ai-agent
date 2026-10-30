# ADR-001 — Adopt the Snow Factory documentation layout

**Status:** Accepted (2026-10-27, maintainer request)

## Context

`docs/` was organised as `guides/`, `models/`, `reference/` and `history/`. The Go services of Snow Factory (reference: `dynamics_microservice/docs`) use one layout: `api/`, `architecture/`, `configuration/`, `decisions/` (ADRs), `deployment/`, `operations/`, `proposals/`, `reference/`, `requirements/`, `rules/` and `security/`.

## Decision

ai-agent uses the same folders. Mapping from the old layout:

| Before | Now |
|---|---|
| `guides/architecture.md` | `architecture/architecture.md` |
| `guides/configuration.md` | `configuration/environment-variables.md` |
| `guides/schemas_and_prompts.md` | `rules/schemas-and-prompts.md` (the rules that make prompts, schemas and `domain/` change together) |
| `guides/debugging_the_flow.md` | `operations/debugging-the-flow.md` |
| `history/refactor_plan.md`, `flows_refactor_plan.md`, `orchestrator_*` | `proposals/PR-001`, `PR-002`, `PR-003-orchestrator-review/` (kept as history, banners unchanged) |
| the API section of `README.md` | `api/api.md` |
| new | `requirements/`, `security/`, `deployment/`, `operations/monitoring.md`, `decisions/` |

The generated tables stay in `docs/models/`: the tests and the scripts in `tests/manual/` read and write them there (`DOC_PATH`).

> **Update 2026-10-27:** `tasks/` was adopted too (README with protocol and board, `ORDER.md`, one folder per epic), for epic T-01 (the `dynamics_microservice` MCP tools), and `setup/questionnaires/` for the questions asked before building (Q01).

Still not adopted: the rest of `setup/` (the Engram intake sub-forms).

Not adopted: `setup/` (the Engram intake sub-forms) and `changes/` (the change report of the Go generator). ai-agent has no code generator and no Engram intake yet.

## Consequences

- Positive: the same place to look in every Snow Factory service.
- Negative: links to the old paths break; they were updated in `README.md`, `CLAUDE.md` and the moved files.
- Rule: a change is not finished until the documents that describe it are true again (`CLAUDE.md`).
