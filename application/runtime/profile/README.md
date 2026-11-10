# application/runtime/profile/

**Level 1 of the runtime: one profile = one run.** A profile (`profiles/<name>.json`) chooses a flow, the models (through a `ModelResolver`), the tools and the prompt overrides.

| File | Contents |
|---|---|
| `runner.py` | `ProfileRunner.run(profile_name, message, history, paused, state, speak_movements, inputs)`: looks the profile up in the `Agent`, picks its `Flow`, starts (or resumes) a `Pipeline` and returns a `FlowResult`. Raises `ProfileMismatch` when the run waiting for the user belongs to another flow. A gesture gets the length of its speech from the reply when no `speech_seconds` was sent. |
| `access.py` | `check_access(agent, name, token)`: a request names a profile (`default` when none) and a token; the profile holds the SHA-256 of the token, compared in constant time. Unknown profile, disabled profile and wrong token are the **same refusal** for the client; the reason (`unknown_or_disabled_profile`, `no_token`, `wrong_token`) is only for the log and never contains the token. `default` needs no token. |
| `inputs.py` | `read_inputs(profile, inputs, reader)`: what a client sends in `inputs` (the `Response` of an earlier profile, or fields such as `reply`). Only the fields the profile `requires` / `accepts`; read with the same code as an LLM answer; raises `InputsError` (`MISSING_INPUT`, `INVALID_INPUT`). Inputs are **data, never instructions**. |

## How it works in the project

`SessionService` calls `check_access` and `read_inputs` before building a `MessageFlowService`, which owns a `ProfileRunner`. The runner is the only thing in the runtime that knows what a profile is; everything below it (flow, step) receives plain objects.
