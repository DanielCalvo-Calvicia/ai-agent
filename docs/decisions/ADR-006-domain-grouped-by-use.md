# ADR-006 — `domain/` grouped by what uses it, one file per concept

**Status:** Accepted (2026-10-05)

## Decision

`domain/entities/` and `domain/value_objects/` each have the subfolders `llm_request/`, `llm_response/` and `movement/`. The domain is pure data: no file or network access, one file per concept, and value objects validate themselves in their `create_*` function.

`application/orchestration/` has five folders with one-way dependencies (`flows`, `phases`, `engine`, `state`, `support`), enforced by `tests/test_orchestration_layout.py`. Every phase is one file that declares its constants first, enforced by `tests/test_phase_structure.py`.

## Consequences

- Positive: easy to find what a part of an answer is made of.
- Negative: a new field in an answer touches the schema, the prompt, the domain object and the response mapper together.
