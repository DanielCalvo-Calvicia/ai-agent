# ADR-002 — ai-agent decides; Brain acts

**Status:** Accepted (2026-09, approximate)

## Context

OBLIVION is a robot made of several services. Something has to understand the user and something has to move the arms and speak.

## Decision

ai-agent only decides and returns a structured answer (`response`, `directives`, `awaiting_user_input`, `flow`). It never controls hardware and never calls stepper, TTS or speaker. `brain_microservice` speaks the answer and moves the arms.

## Consequences

- Positive: the agent can be tested with scripted LLMs and no hardware; a bad answer cannot move anything by itself.
- Negative: the movement flow has only been exercised with fake hardware.
