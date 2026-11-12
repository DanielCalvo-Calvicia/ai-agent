# application/runtime/step/

**Level 3 of the runtime: one step.** A step is either an LLM call (declared in `step_defs/<name>.json`) or a piece of plain code (`library/`).

| File / folder | Contents |
|---|---|
| `spec.py` | `PhaseSpec` (one LLM call with the step's whole answer schema), `ActionPhaseSpec` (one LLM call per planned action) and `Step` (one position of a pipeline: `run`, `pause_if`, `phase_id`, `retry_on_status`). |
| `runner.py` | `PhaseRunner`: **the only place an LLM payload is built and sent** through `LLMOutboundPort`. Builds the system prompt, picks the model list, retries and falls back to the next model on a lack of capacity (ADR-014), classifies failures and records token usage in the metrics. |
| `declared.py` | Builds a `PhaseSpec` / `ActionPhaseSpec` from a declaration: prompt file, intent, format, answer pieces from `schema/response/`, `reads` and `writes` (fields of `config/state_fields.json` only). Loads `step_defs/*.json`. |
| `functions.py` | The named functions a declaration may use when a plain list of fields is not enough (`planner_input`, `safety_input`, `message_with_history`, `movement_from`, `emotion_result`, ...). |
| `build.py` | `build_step_function(name, ...)`: the function a flow runs for a step name (declared LLM step, or the `run` / `build_step` of a code step). |
| `registry.py` | Registry of every step (`register_step`, `all_steps`, `step`): code steps register themselves from their file; LLM steps enter from their declaration. Name and legacy phase id must be unique. |
| `catalog.py` | `PHASES` and `CONVERSATION_PHASES` tables (id, step name, default model, prompt file) read from the registry; used by the prompt loader, model selection and metrics. |
| [`library/`](library/README.md) | The steps that are Python code, and the two prompts the runtime runs itself. |

## How it works in the project

`Pipeline` asks `build_step_function` for each step in the flow file. An LLM step reads its fields from the `FlowState`, calls `PhaseRunner.run_phase`, and writes the answer back into the state. Adding an LLM step = one JSON declaration plus one prompt (`tests/test_step_declarations.py`); adding a code step = one file in `library/<group>/` that registers itself (`tests/test_phase_structure.py`).

A step never imports a profile, a flow or `assembly/`.

## `system_prompt.py`: the system message of every LLM step (was `application/system_prompts/general.py`, moved 2026-11-12)

Builds the **system message** every LLM step sends.

| File | Contents |
|---|---|
| `system_prompt.py` | `build_system_prompt_from_file(prompt_file, clock, override, step_text)` joins, in this order: the generic rules (`prompts/0_generic_prompt.txt`), what the robot can and cannot do (`prompts/capabilities.txt`), `CURRENT DATE AND TIME: ...` (from `application/support/clock.py`) and the step's own prompt. `build_system_prompt(phase)` and `LoadSystemPrompt(phase)` do the same by phase number; `prompt_file_of` looks the file up in `catalog.py`. |

## How it works in the project

- `PhaseRunner` (`runtime/step/runner.py`) calls `build_system_prompt_from_file` for each call. The profile may change the step's part with a `PromptOverride` (`prompt_replace` / `prompt_append`, `support/llm/prompt_overrides.py`); the generic rules, the capabilities and the date always stay in front.
- The step's prompt text normally comes from the configuration source (`Agent.step_prompts`); with no text it is read from the repository.
- Files are resolved from the project root, not from the working directory.
- The prompt files live in `prompts/` at the project root. A change to a prompt changes the golden file (`UPDATE_GOLDEN=1`, on purpose) and needs `docs/rules/schemas-and-prompts.md` updated.
| `metrics.py` | `SessionMetrics`, `TokenCount`: one record per LLM call (`RequestRecord`, in `domain/value_objects/usage/`) with `profile`, `flow`, `step`, `model`, `client`, tokens, `cost_usd` and `profile_hash`; totals by any key (`total_by`); forwards records to a `UsageReporterPort`. Holds no token, input, tool argument or tool answer. Moved here from `support/` on 2026-11-12 (it reads the step catalog). |
| `model_selection.py` | `ModelResolver`, `effective_models`, `check_model_set`: which models answer a step, as an ordered list (ADR-014). Moved here from `support/llm/` on 2026-11-12 (it reads the step catalog). |
