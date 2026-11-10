# application/service/

The services that implement the inbound ports. They own **sessions and one message**; they do not know any flow or step (that is `runtime/`).

| File | Class | Responsibility |
|---|---|---|
| `session_service.py` | `SessionService` | Implements `SessionInboundPort`. Keeps sessions **in process memory only** (`SessionService.sessions`, lost on restart). `start_session` / `end_session` create and drop a `UserSession`. `message_received` resolves the request: the profile and its token (`runtime/profile/access.py`), the question being answered (`pause_id`, `PROFILE_MISMATCH`, `PAUSE_NOT_FOUND`), the `inputs` (`runtime/profile/inputs.py`) and `return`; runs the agent; stores the history entry and the run waiting for the user; and builds the answer DTO. Failures become a speakable apology (`response`) plus a technical `message` and an `error_code` (`SESSION_NOT_FOUND`, `INVALID_PROFILE`, `MISSING_INPUT`, `INVALID_INPUT`, ...). |
| `message_flow_service.py` | `MessageFlowService` | Implements `MessageInboundPort`. **One instance per message.** Owns the `SessionMetrics` of the message and a `ProfileRunner`; `text()` begins the metrics, runs the profile and returns a `TextResponseDTO` (reply, movements, gesture, `awaiting_user_input`, flow). After a run it exposes `paused_run` and `last_response`. |
| `user_session.py` | `UserSession` | One started session: ids, the last requests (`HistoryEntry`, trimmed to `AI_AGENT_HISTORY_TURNS`), the `PausedRun` waiting for the user, its `pause_id` and the profile that asked. `history` derives the messages the steps read. |

## How they work in the project

```text
SessionService.message_received
   -> check_access / read_inputs / pause checks
   -> MessageFlowService(...).text()
        -> ProfileRunner.run(profile, message, history, paused, inputs=...)
   <- TextResponseDTO -> MessageReceivedResponseDTO
```

- A run that asked the user a question is resumed by the next message **of the same profile** carrying the same `pause_id`.
- A request that adds no `user_goal` to the run (gesture, a movement nobody classified) adds no history entry.
- Nothing here logs the user's words, a token or an input.
