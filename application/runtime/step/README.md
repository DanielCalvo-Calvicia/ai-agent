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
