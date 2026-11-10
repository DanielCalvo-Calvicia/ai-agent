# application/runtime/step/library/common/

Steps that **any flow that can pause** uses. They are run by the runtime, not listed in a flow file.

| File | Phase | Contents |
|---|---|---|
| `answer_checker.py` | 9 | `make_answer_checker(paused, user_reply)` builds the `PhaseSpec` that decides whether the user's reply answers the question. Defines the verdicts `ANSWERED`, `CONFIRMED`, `DECLINED`, `NOT_ANSWERED`, `STOP`. Prompt: `prompts/9_answer_checker.txt`. Asks in the user's language. |
| `user_clarification.py` | 99 | Constants only: model, intent, temperature, token limit, the default message and the system prompt (a constant, no prompt file, plain-text answer). |

Both are consumed by `runtime/flow/pause/` (`AnswerChecker`, `Clarifier`). They default to the cheap `gemini-3.1-flash-lite` and a model set can change them.
