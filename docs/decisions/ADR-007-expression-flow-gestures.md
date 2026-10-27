# ADR-007 — Expression flow: an emotional arm gesture for replies

**Status:** Accepted (2026-10-08); implemented in `ce1acde`

## Context

A spoken reply with a still robot looks flat.

## Decision

With `AI_AGENT_EXPRESSION` on (default), after the conversation or special flow has written its reply, the router runs the `expression` flow on it: `emotion_reader` (phase 30, one cheap model call: `emotion`, `intensity` 1 to 5, up to 3 optional movements) and `gesture_builder` (phase 31, plain code). The gesture is random arm movements shaped by the emotion (`domain/operations/gesture.py`), with `pause_seconds` between them, about as long as the speech (`AI_AGENT_SPEECH_CHARS_PER_SECOND`), every arm back where it started. It goes out as `directives` with `gesture: true`, checked by the motion validator.

The reply is never held back: if the expression flow fails or the validator refuses the gesture, the reply goes out without one. A movement the user asked for gets no gesture. `AI_AGENT_EXPRESSION_SEED` makes gestures repeatable in tests.

## Consequences

- Positive: more expressive answers for one extra cheap call per reply.
- Negative: extra latency and cost per reply; never run against a real LLM yet.
