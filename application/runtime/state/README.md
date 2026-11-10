# application/runtime/state/

**The data that travels through a run.** Steps read and write fields of the state; nothing else is shared between steps.

| File | Contents |
|---|---|
| `flow_state.py` | `FlowState`: the user `message`, earlier turns (`history`) and one field per section of the LLM answer (`intent`, `user_goal`, `task_category`, `actions`, `missing_information`, `constraints`, `safety_and_validation`, `next_step`, ...), plus helpers (`final_text()`, `needs_user_input()`, `as_response()`). `strip_markup` removes stray tags a model may leak, because the reply is spoken aloud. |
| `motion_state.py` | `MotionFlowState` (movement flow): the movement sequence, `motion_rejection`, `spoken_reply`, `speak_movements`; `as_motion` checks the type. |
| `expression_state.py` | `ExpressionFlowState` (gesture flow): `reply`, `speech_seconds`, `emotion`, `intensity`, improvised and built movements; `as_expression`. |
| `paused_run.py` | `PausedRun` (everything needed to continue where a flow stopped) and `FlowResult` (reply, paused run, movements, flow name, final state, `ended_early`, `gesture`). |
| `history.py` | `HistoryEntry` (words, reply, structured `Response`), `messages_of` (what steps read) and `response_of` (the `Response` of a run, or `None` without a `user_goal`). Entries are never logged. |
| `response_json.py` | `response_to_json`: a `Response` as plain data, the shape a client reads in `output` and sends back in `inputs`. Token usage and raw model text stay inside. |

## How it works in the project

- The fields a step may read and write are the catalog `config/state_fields.json`; a test keeps it equal to these classes.
- The flow decides which state class a run starts with (`runtime/flow/hooks.py`).
- `SessionService` keeps `HistoryEntry` objects per session (`AI_AGENT_HISTORY_TURNS`).
