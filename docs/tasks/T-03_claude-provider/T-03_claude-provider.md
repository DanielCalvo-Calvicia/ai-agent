# T-03 — Claude as a provider

| | |
|---|---|
| Status | in-progress (created 2026-10-28; T-03.1 to T-03.5 done; T-03.6 run twice: one wrong reply on Haiku, all right with Sonnet for planner, writer and editor) |
| Kind | epic |
| Parent | project |
| Depends on | T-02 (the catalog and the profiles) |
| Blocks | — |

> Source: the trial of 2026-10-28 with the Anthropic key of the maintainer, and [ADR-013](../../decisions/ADR-013-claude-through-sanitized-structured-outputs.md).

## Goal

The agent runs on Claude models through Anthropic's OpenAI-compatible endpoint, with a profile to switch to it. It was not possible before: every call got a 400.

## What exists and what changes

| Today | After T-03 |
|---|---|
| Every Claude call fails: the endpoint needs `strict: true` and refuses the real schemas (F18, F19) | A Claude model receives a sanitized copy of the schema with `strict: true` (`anthropic_schema.py`) |
| The Claude entries of the price file say "needs adapter change" | `claude-haiku-4-5` is `tested`; the Sonnet entries `should work, untested` |
| Profile `claude_sonnet` only, never run | Also `claude_haiku` and `claude_mixed` (not active), each run once |
| No Claude call was ever made by the agent | Two real runs: 10 and 13 calls, no error |

## Subtasks

| Order | Task | Kind | Status |
|---|---|---|---|
| 1 | [T-03.1 Decisions](T-03.1_decisions.md) | decision | done (2026-10-28) |
| 2 | [T-03.2 The sanitizer and its wiring](T-03.2_sanitizer-and-wiring.md) | code | done (2026-10-28) |
| 3 | [T-03.3 Tests](T-03.3_tests.md) | test | done (2026-10-28) |
| 4 | [T-03.4 Profile, price notes, generated tables](T-03.4_profile-and-price-notes.md) | code | done (2026-10-28) |
| 5 | [T-03.5 Documentation and ADR-013](T-03.5_documentation.md) | docs | done (2026-10-28) |
| 6 | [T-03.6 First real run on Claude](T-03.6_first-real-run-on-claude.md) | manual | in-progress (run twice; the second, with Sonnet, all right; a Business Central request ran on `claude_mixed` on 2026-10-29) |
| 7 | [T-03.7 Prices of the other Claude ids](T-03.7_prices-of-the-other-claude-ids.md) | code | done (2026-10-29) |

## Exit criteria

A Claude profile answers a conversation message, a task with a plan, a movement and a Business Central request correctly; the suite passes; the documents are true; the maintainer closes it after reading T-03.6.

## Rules that bind every task of this epic

- Dependencies go one way: the sanitizer lives in `infrastructure/outbound/llm/`; `domain/` and `application/` do not know it.
- The schemas, the prompts, the domain objects and what the other providers receive do not change.
- A real call only when the maintainer asks (it costs money on this key).
- Never read, print or copy a `.env` value.
- Commit and push only when asked.
- The baseline of the [tasks README](../README.md) section 3.

## Open points

- The reply to a greeting on `claude-haiku-4-5` (known gap 13 of the requirements).
- A plan, the Business Central tools and the Sonnet planner were not run on Claude.
- Whether to make Claude the profile of T-01.9 (decided there).
