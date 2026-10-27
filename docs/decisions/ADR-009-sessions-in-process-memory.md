# ADR-009 — Sessions live in process memory only

**Status:** Accepted (2026-09, approximate)

## Decision

`SessionService.sessions` holds the sessions and the run waiting for the user. Nothing is persisted and nothing expires a session before `/session/end`. `error_code == "SESSION_NOT_FOUND"` means exactly that the session is not here; the caller opens a new one and resends the message once.

## Consequences

- Positive: no storage to run; simple.
- Negative: a restart loses every session and paused run; more than one instance would not share sessions.
