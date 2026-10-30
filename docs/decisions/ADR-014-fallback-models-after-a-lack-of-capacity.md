# ADR-014 — Fallback models after a lack of capacity, per profile

**Status:** Accepted (2026-10-29, at the maintainer's request). Built in epic [T-04](../tasks/T-04_llm-resilience/T-04_llm-resilience.md).

## Context

On 2026-10-28 the free-tier models failed in two ways: `gemini-3.1-flash-lite` answered 503 "high demand" on every try (the message failed after four minutes), and `gemini-3-flash-preview` answered 429 with a quota of 20 requests per day. The runner retried at once, three times, and then apologised.

## Decision

1. A call that fails for lack of capacity (429, any 5xx, timeout, no connection) waits `AI_AGENT_RETRY_WAIT_SECONDS` (default 1, doubling, capped at 8 times) before the next try; a 429 that says "per day" stops the tries on that model.
2. Then the `fallback_models` of the **active profile** are tried once each, in order (`AI_AGENT_FALLBACK_MODELS` overrides). The first answer wins and is recorded under its own model.
3. `proven` and `google_free` list `gemini-3.5-flash-lite` and `gemini-3-flash-preview`. The Claude profiles list none.
4. When nothing answers, the failure is the chosen model's, so the apology and its category do not change.

## Consequences

- A free-tier hiccup no longer costs the message, at the price of a second model seeing the same prompt: with the Google free tier that is the same provider and the same policy.
- The fallback is per profile on purpose: customer data from a Claude profile must not go to another provider (the Google free tier trains on its content) because one model had a bad minute. A profile that wants a fallback names it.
- The cost of a message can rise (a second call), and the cost tables use the chosen model's prices.
- The SDK under the adapter still has its own retries; a slow 503 can still take a while before the runner sees it.
- Not done: a circuit breaker, a fallback for the MCP tools, `Retry-After`.
