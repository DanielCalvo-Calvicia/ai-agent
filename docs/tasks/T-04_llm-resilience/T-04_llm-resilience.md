# T-04 — A model out of capacity does not stop the message

| | |
|---|---|
| Status | done (2026-10-29; the real behaviour on a 503 was not provoked, see Notes) |
| Kind | epic |
| Parent | project |
| Depends on | T-02 (the Google profiles) |
| Blocks | — |

> Source: the real runs of 2026-10-28 (T-02.10): `gemini-3.1-flash-lite` answered 503 "high demand" on every try and the message failed after four minutes; `gemini-3-flash-preview` answered 429 "20 requests per day". The maintainer said "Not now" that day and asked for it on 2026-10-29.

## Goal

When the chosen model is out of capacity, the agent waits a little, then asks another model, and only then apologises.

## What exists and what changes

| Today | After T-04 |
|---|---|
| A failed LLM call is retried at once, up to `AI_AGENT_MAX_ATTEMPTS`, with no wait, and then the message fails | Waits (`AI_AGENT_RETRY_WAIT_SECONDS`, doubling, only after a lack of capacity), then tries the `fallback_models` of the active profile once each |
| A daily quota (Google 429 "per day") is retried three times for nothing | Goes to the next model at once |
| Every 5xx is "unknown" in the apology | Unchanged: the category stays; only the fallback treats it as a lack of capacity |

## Subtasks

| Order | Task | Kind | Status |
|---|---|---|---|
| 1 | [T-04.1 Decisions](T-04.1_decisions.md) | decision | done (2026-10-29) |
| 2 | [T-04.2 Wait, fallback models and the runner](T-04.2_wait-and-fallback.md) | code | done (2026-10-29) |
| 3 | [T-04.3 Tests and documentation](T-04.3_tests-and-documentation.md) | test | done (2026-10-29) |

## Exit criteria

A call that fails for lack of capacity is answered by a fallback model and recorded under the model that answered; an error that is not a lack of capacity never falls back; the suite passes; the documents are true.

## Rules that bind every task of this epic

- Dependencies go one way: the wait and the capacity test are in `support/failure.py`, the list in `support/model_selection.py`, the loop in `engine/phase_runner.py`.
- A profile that uses a paid or private provider (the Claude profiles) has **no** fallback: customer data must not move to another provider because one had a bad minute.
- No real call. Commit and push only when asked.
- The baseline of the [tasks README](../README.md) section 3.

## Open points

- Nothing provoked a real 503: the behaviour is covered with scripted errors only.
- The SDK underneath (`ai_sdk`, the OpenAI client) has its own retries; they were not changed.
