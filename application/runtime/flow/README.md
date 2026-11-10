# application/runtime/flow/

**Level 2 of the runtime: the steps of one flow.** A flow is a JSON file (`flows/<name>.json`); this folder holds the Python that runs it and the fixed lists of names a flow file may use.

| File / folder | Contents |
|---|---|
| `flow.py` | `Flow` (name, how to build its steps, result builder, initial state, `on_pause` / `on_resume`, tool limits) and `FlowContext` (what the steps are built with). |
| `pipeline.py` | `Pipeline`: runs the steps in order; retries a step while it says `retry` / `error` (`retry_on_status`); evaluates `pause_if`; **stops to ask the user** when a step leaves the flow waiting; resumes the paused run when the next message answers the question; handles stop and decline; builds the per-step `ToolScope`. Knows no particular flow. |
| `conditions.py` | `CONDITIONS`: the named conditions a flow file may put in `pause_if` (today `needs_user_input`). A flow cannot invent one. |
| `hooks.py` | `HOOKS` (`user_clarification` on pause, `answer_checker` on resume), the result builders (`reply_of_the_state`, `nothing_to_say`, `movements_of_the_state`, `gesture_of_the_state`) chosen by `result_from`, and the state a flow starts with (`FlowState`, `MotionFlowState` or `ExpressionFlowState`). |
| [`pause/`](pause/README.md) | Asking the user and reading the answer. |

## How it works in the project

`assembly/flow_file.py` turns a flow file into a `Flow`; `assemble()` checks that every name used (steps, conditions, hooks) exists. At run time `ProfileRunner` hands the flow to a `Pipeline`, which runs each step through `runtime/step/`. Adding a condition or a hook means writing it here in Python and adding it to the table.
