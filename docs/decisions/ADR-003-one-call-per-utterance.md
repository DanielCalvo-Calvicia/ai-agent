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
