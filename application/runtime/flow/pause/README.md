# application/runtime/flow/pause/

What happens when a flow **needs something from the user** and when the user replies. Used by any flow that can ask (`on_pause` / `on_resume` in its file).

| File | Class | What it does |
|---|---|---|
| `clarification.py` | `Clarifier` (phase 99) | When a step leaves missing inputs, collects `next_step.requested_user_input` and `actions[].required_inputs` and makes one cheap LLM call that writes a short, friendly question. Without inputs it returns a default message. |
| `answer_check.py` | `AnswerChecker` (phase 9) | The next message arrives while a run is paused. One LLM call decides the verdict: `answered`, `confirmed`, `declined`, `not_answered` or `stop`; the verdict is always one that fits the kind of question (`INPUT` or `CONFIRMATION`). |

## How it works in the project

1. A step writes a question into the state; the flow's `pause_if: needs_user_input` fires.
2. `Pipeline` calls the `Clarifier`, stores a `PausedRun` (state, step index, kind, question, flow) and returns the question with `awaiting_user_input = true`.
3. `SessionService` keeps the `PausedRun` and a `pause_id`; the client sends the answer with that id.
4. `Pipeline` calls the `AnswerChecker` and continues from the step that was waiting, asks again, or ends early.

The prompts these two use are run by the runtime itself (`runtime/step/library/common/`).
