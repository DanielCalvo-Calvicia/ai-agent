# docs/ of ai-agent

Four folders. Only `guides/` describes how the code works today.

```text
docs/
  guides/      written by hand, kept in step with the code
  models/      generated tables of models, prices and costs (do not edit by hand)
  reference/   notes on the model catalog
  history/     plans and reviews that explain why, not how it is laid out now
```

## `guides/`: current

| File | What it is |
|---|---|
| [`architecture.md`](guides/architecture.md) | the reference: the request path, the four flows and the router, the phases, the engine, the state, `domain/`, `infrastructure/`, how to extend it |
| [`schemas_and_prompts.md`](guides/schemas_and_prompts.md) | the prompts, the two schema trees (`general`, `motion`), the generator, how to change an answer |
| [`configuration.md`](guides/configuration.md) | every environment variable, which model answers each step, MCP servers, retries and failures, Langfuse |
| [`debugging_the_flow.md`](guides/debugging_the_flow.md) | tracing and debugging a message step by step (`tests/manual/debug_flow.py`, `debug_break.py`) |

When you change the code, change the matching guide in the same commit. If a guide and the code disagree, the code is right.

## `models/`: generated

| File | Written by |
|---|---|
| [`gemini_models_per_step.md`](models/gemini_models_per_step.md) | `tests/manual/show_models.py --write`, from `config/gemini_models.json` |
| [`models_per_step_budget.md`](models/models_per_step_budget.md) | `tests/manual/show_models.py --budget`, from `config/*.json` and the budget |
| [`cost_of_a_full_plan.md`](models/cost_of_a_full_plan.md) | `tests/manual/estimate_cost.py --write` |

## `reference/`: notes

| File | What it is |
|---|---|
| [`github_models.md`](reference/github_models.md), [`model_catalog_notes.md`](reference/model_catalog_notes.md) | notes on the model catalog (ids and providers as the author listed them; GitHub Models is retired) |
| [`model_recomended_per_phase.md`](reference/model_recomended_per_phase.md) | an early, unmeasured recommendation table |

## `history/`: not documentation of the current design

| File | What it is |
|---|---|
| [`orchestrator_report.md`](history/orchestrator_report.md), [`orchestrator_questionnaire.md`](history/orchestrator_questionnaire.md), [`orchestrator_decisions.md`](history/orchestrator_decisions.md) | the review of 2026-09-21 of the single-pipeline design and the owner's answers |
| [`refactor_plan.md`](history/refactor_plan.md) | the refactor that made the code layered (2026-09) |
| [`flows_refactor_plan.md`](history/flows_refactor_plan.md) | the split into conversation-flow and motion-flow (2026-09-30), **replaced on 2026-10-05 by the four flows** described in `guides/architecture.md` |

The history files keep the old names (`conversation-flow`, `motion-flow`, `fast_path`, `robot_context`, `Pipeline` with one flow) and old
paths. Read them for the reasons behind a decision, never for how the code is laid out.
