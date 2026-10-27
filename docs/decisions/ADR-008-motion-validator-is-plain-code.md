# ADR-008 — The motion validator is plain code

**Status:** Accepted (2026-10-05); limits raised in `c467eef` (2026-10-08)

## Decision

Phase 21 `motion_validator` makes no LLM call. It checks the arm and the direction, the degrees of each movement and the sequence: at most 20 movements and 3600 degrees in total. One bad movement refuses the whole sequence and the refusal is always said to the user. The limits are constants at the top of the file. The gesture builder's output goes through the same validator.

## Consequences

- Positive: what reaches Brain is checked by deterministic code, not by a model.
- Negative: the limits are a judgement and were never tried on the real hardware.
