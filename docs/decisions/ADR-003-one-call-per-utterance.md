# ADR-003 — Brain makes one call per utterance

**Status:** Accepted (2026-10-05)
**Replaces:** the design of 2026-09-30 in which Brain asked two flows (`conversation-flow`, `motion-flow`) one after the other ([PR-002](../proposals/PR-002-flows-split.md)).

## Context

Asking two agents in order doubled the calls and left the decision of "which one answers" to Brain.

## Decision

Brain sends each utterance once to `POST /session/message`. ai-agent decides which flow answers. Brain's `AI_AGENT_FLOWS` and ai-agent's `AI_AGENT_FAST_PATH_ENABLED` were removed. `speak_movements` is Brain's own setting and arrives with every message.

## Consequences

- Positive: one HTTP call, one answer; `flow` says who answered.
- Negative: ai-agent owns the routing, and its quality depends on triage (see [ADR-004](ADR-004-four-flows-behind-one-router.md)).

**Note 2026-11-04, [ADR-015](ADR-015-profiles-flows-steps.md):** the decision that ai-agent decides which flow answers inside one call is **replaced**. The client now chooses the profile on every request and chains them (`identification`, then the profile of the answer); the service does not route. Brain still sends one call with no profile and gets the `default` profile (no movement, no gesture) until it is changed. The rest stands: `speak_movements` is Brain's setting and arrives with every message.
