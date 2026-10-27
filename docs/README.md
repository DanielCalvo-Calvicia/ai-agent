# docs/ of ai-agent

Same layout as the other Snow Factory services ([ADR-001](decisions/ADR-001-adopt-documentation-standard.md)). Status 2026-10-27: the four-flow redesign and the expression flow are merged into `feature` (PR #3); the documents describe that code.

When you change the code, change the matching document in the same piece of work. If a document and the code disagree, the code is right: fix the document.

```text
docs/
  api/            the HTTP routes and the answer
  architecture/   how the code works
  configuration/  every environment variable, models per step, MCP servers
  decisions/      ADRs
  deployment/     how it runs
  operations/     monitoring, failures, debugging
  proposals/      plans and reviews that explain why (history)
  reference/      notes on the model catalog
  requirements/   what the service must do and its state
  rules/          what must change together (prompts, schemas, domain)
  security/       secrets, exposure, data sent to third parties
  models/         generated tables of models, prices and costs (do not edit by hand)
```

## Current

| File | What it is |
|---|---|
| [`api/api.md`](api/api.md) | routes, the envelope, `/session/message`, sessions, `SESSION_NOT_FOUND` |
| [`architecture/architecture.md`](architecture/architecture.md) | the request path, the four flows and the router, the phases, the engine, the state, `domain/`, `infrastructure/`, how to extend it |
| [`configuration/environment-variables.md`](configuration/environment-variables.md) | every variable, which model answers each step, MCP servers, retries, Langfuse |
| [`rules/schemas-and-prompts.md`](rules/schemas-and-prompts.md) | the prompts, the two schema trees (`general`, `motion`), the generator, how to change an answer |
| [`requirements/requirements.md`](requirements/requirements.md) | functional and non-functional requirements with their status and the known gaps |
| [`security/security.md`](security/security.md) | secrets, what the service can do, data that leaves it |
| [`deployment/deployment.md`](deployment/deployment.md) | run it, what it needs, state; the delivery lives outside this repository |
| [`operations/monitoring.md`](operations/monitoring.md) | probes, logging, metrics, Langfuse, failures |
| [`operations/debugging-the-flow.md`](operations/debugging-the-flow.md) | tracing and debugging a message step by step (`tests/manual/debug_flow.py`, `debug_break.py`) |
| [`decisions/`](decisions/) | ADR-001 to ADR-010 |

## `models/`: generated

They stay in `docs/models/` because the tests and the scripts of `tests/manual/` read and write them there.

| File | Written by |
|---|---|
| [`gemini_models_per_step.md`](models/gemini_models_per_step.md) | `tests/manual/show_models.py --write`, from `config/gemini_models.json` |
| [`models_per_step_budget.md`](models/models_per_step_budget.md) | `tests/manual/show_models.py --budget`, from `config/*.json` and the budget |
| [`cost_of_a_full_plan.md`](models/cost_of_a_full_plan.md) | `tests/manual/estimate_cost.py --write` |

## `reference/`: notes

| File | What it is |
|---|---|
| [`github-models.md`](reference/github-models.md), [`model-catalog-notes.md`](reference/model-catalog-notes.md) | notes on the model catalog (ids and providers as the author listed them; GitHub Models is retired) |
| [`model-recommended-per-phase.md`](reference/model-recommended-per-phase.md) | an early, unmeasured recommendation table |

## `proposals/`: history, not the current design

| File | What it is |
|---|---|
| [`PR-001-layered-refactor.md`](proposals/PR-001-layered-refactor.md) | the refactor that made the code layered (2026-09) |
| [`PR-002-flows-split.md`](proposals/PR-002-flows-split.md) | the split into conversation-flow and motion-flow (2026-09-30), **replaced on 2026-10-05 by the four flows** ([ADR-004](decisions/ADR-004-four-flows-behind-one-router.md)) |
| [`PR-003-orchestrator-review/`](proposals/PR-003-orchestrator-review/) | the review of 2026-09-21 of the single-pipeline design (`report.md`, `questionnaire.md`) and the owner's answers (`decisions.md`) |

The proposals keep the old names (`conversation-flow`, `motion-flow`, `fast_path`, `robot_context`, `Pipeline` with one flow) and old paths. Read them for the reasons behind a decision, never for how the code is laid out.
