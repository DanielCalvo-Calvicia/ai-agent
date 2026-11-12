# ADR-016 — The application folders follow the path of a message: `runtime/` (profile, flow, step, state), `assembly/` and `support/`

**Status:** Accepted and built (2026-11-09, by the maintainer; task [T-06.8](../tasks/T-06_redesign/T-06.8_runtime-folder-layout.md)). It changes only where files live: no behaviour, prompt, schema or model changed, the golden file is untouched. It refines the layering of [ADR-015](ADR-015-profiles-flows-steps.md) (profile -> flow -> step) into folders.

## Context

`application/engine/` held four different things (what runs a message, how a run pauses, what builds the agent at start, what checks the request) and `application/steps/` held both the machinery that builds a step and the steps that are code. `state/` and `support/` lived inside `engine/`. It was hard to tell what a folder was for, and a step's shape (`PhaseSpec`) was in a different folder from the runner that uses it.

## Decision

The runtime is the path of a message, one folder per level, and a level uses only the ones below it: **`runtime/profile` -> `runtime/flow` -> `runtime/step` -> `runtime/state` -> `support`**. Start-up code is its own folder, `assembly/`, which may use everything; the runtime reads only `runtime/profile/assembled.py` (`Agent`, `AssembledProfile`, `DEFAULT_PROFILE`, plain data taken out of `assemble.py`). The steps that are Python code are `runtime/step/library/<group>/`. `tests/test_orchestration_layout.py` enforces the direction.

| Before | After |
|---|---|
| `engine/profile_runner.py`, `profile_access.py`, `profile_inputs.py` | `runtime/profile/runner.py`, `access.py`, `inputs.py` |
| `engine/flow.py`, `pipeline.py`; `steps/conditions.py`, `steps/hooks.py` | `runtime/flow/flow.py`, `pipeline.py`, `conditions.py`, `hooks.py` |
| `engine/clarification.py`, `answer_check.py` | `runtime/flow/pause/clarification.py`, `answer_check.py` |
| `engine/phase_runner.py`; `steps/phase.py` | `runtime/step/runner.py`, `spec.py` |
| `steps/{declared,build,functions,registry,catalog}.py` | `runtime/step/` (same names) |
| `steps/{common,special,movement,expression}/` | `runtime/step/library/{common,special,movement,expression}/` |
| `engine/state/` | `runtime/state/` |
| `engine/{assemble,config_snapshot,flow_file}.py` | `assembly/` (same names); `Agent`, `AssembledProfile` -> `runtime/profile/assembled.py` |
| `engine/support/{model_selection,schemas,prompt_overrides,failure}.py` | `support/llm/` |
| `engine/support/{action_tree,mcp_servers}.py` | `support/tools/` |
| `engine/support/{metrics,clock,expression_settings}.py` | `support/` |

## Consequences

- Every import of `application.engine.*` and `application.steps.*` changed; the step registry now scans `runtime/step/library/`. The JSON folders at the root (`flows/`, `step_defs/`, `profiles/`, `model_sets/`, `prompts/`) did not move.
- One exception stayed: `support` read `runtime/step/catalog.py` (the tables of metrics and model selection), as it read `steps/catalog.py` before.
- **Note 2026-11-12 (clean-architecture pass)**: the exception is gone and the cycles with it. `metrics.py` and `model_selection.py` moved to `runtime/step/`; `application/system_prompts/general.py` became `runtime/step/system_prompt.py`; `assembly/model.py` became `runtime/profile/assembled.py` (the runtime no longer imports `assembly/`). The data of the ports moved to `domain/`, the application is given its files and settings through two ports (`support/environment.py`), and `tests/test_clean_architecture.py` enforces the rule.
- **Note 2026-11-12 (domain use)**: `infrastructure/` no longer imports `domain/`. `application/dtos/outbound/` exposes the domain's own classes to the outbound adapters, `application/mappers/` holds the conversions (`response_mapper.py` moved there from `infrastructure/outbound/llm/`, and the message request and answer DTOs are built by `mappers/inbound/message_mapper.py`), and `domain/operations/` stays for logic over domain objects only.
- The history (tasks, proposals, ADRs written before 2026-11-09) names the old paths; this table translates them. It is not rewritten.
- **Note 2026-11-12 (LLM adapter folders)**: `infrastructure/outbound/llm/` is split by who knows the SDK: `vercel/` holds the only code that imports `ai_sdk` (`adapter.py`, `messages.py`, `options.py`, `models.py`, `tool_adapter.py`), and `shared/providers/`, `shared/tools/` and `shared/schemas/` do not (`tests/test_llm_layout.py`). `VercelAIConfig` became `LLMConfig`; `provider_models.py` is `vercel/models.py` plus `shared/providers/routes.py`; `tools.py` is `shared/tools/resolver.py` plus `vercel/tool_adapter.py`. No behaviour changed.
