# ADR-013 — Claude through Anthropic's OpenAI-compatible endpoint, with a sanitized strict schema

**Status:** Accepted (2026-10-28, at the maintainer's request to try Claude with the only paid key at hand, an Anthropic one). Built in epic [T-03](../tasks/T-03_claude-provider/T-03_claude-provider.md); run once on real messages (T-03.6).

## Context

`ai_sdk`'s Anthropic provider is the OpenAI SDK pointed at `https://api.anthropic.com/v1/`. The model catalog, the prices and a `claude_sonnet` profile already existed, but no Claude call had ever worked in this agent: the notes in `config/other_models.json` said "needs adapter change". Anthropic's documentation says that endpoint ignores `response_format`. Measured on 2026-10-28 with the project's key:

- every call of the agent got a 400, "response_format.json_schema.strict: Field required"; `strict: false` is refused too ("Input should be True"). So the endpoint does honour `response_format`, but only as structured outputs with `strict: true`;
- without a schema Claude answered with the JSON inside a code fence every time and invented values outside the allowed ones (`"primary": "greeting"`, a string where an array was expected), which the answer mapper refuses;
- with `strict: true` the real schemas of the phases are refused as they are: objects without `additionalProperties: false`, number limits (`minimum`, `maximum`), `maxItems`, and the recursive `action` reference ("Circular reference detected in schema definitions: action -> action") of the planner and the three action steps.

## Decision

1. **A Claude model receives a sanitized copy of the schema, sent with `strict: true`** (`infrastructure/outbound/llm/anthropic_schema.py`, called from `_build_options` of `vercel.py` only when `payload.model.is_anthropic()`): `additionalProperties: false` on every object; the keywords Anthropic refuses removed; `minItems` capped at 1; the recursive reference unrolled to **3 levels** (an action and two levels of subactions). All 10 phase schemas were accepted by Anthropic with it and returned valid JSON.
2. **Nothing else changes.** The schemas, the prompts, the domain objects, the answer mapper and what every other provider receives are as they were; the golden file does not change.
3. **A profile, not a default.** `claude_haiku` (`claude-haiku-4-5` on every step, `claude-sonnet-5-5` for the planner) is added and is not active. The code defaults and the active profile stay Google's (ADR-012). *Note 2026-10-28:* `claude_mixed` was added (Sonnet 5.5 for the planner, the draft writer and the editor), because `claude_haiku` answered one greeting with a description of the reply; it is not active either.
4. **The cost tables are not corrected for thinking.** Claude 5 models think by default and the endpoint hides it; the estimates count visible tokens only.

## Consequences

- Positive: Claude runs the agent end to end with the key at hand: three messages (a greeting, a request for tips, a movement) gave 10 calls and no error or warning, about 2.7 cents at Haiku 4.5 prices (T-03.6).
- Negative: the planner cannot nest subactions deeper than 3 levels on Claude; the schema adds about 2.8k input tokens to each call of the four actions steps; the first call of each schema is slow (10 to 14 s, then about 2 s); Anthropic calls this endpoint a layer for testing, not for production; the forced tool use is not supported by Sonnet 5.5 and Opus 5.5 (not checked in the agent's tool step); thinking cannot be turned off on Sonnet 5.5.
- A quality problem seen in the first run, not fixed: on `claude-haiku-4-5` the greeting was answered with a description of the reply instead of the reply.
- Not run: a plan, a tool call (the Business Central tools with Claude are T-01.9), the Sonnet planner.

## Alternatives not taken

- **The prompt alone, with a tolerant reading of the JSON:** tried (a throw-away patch): the fences were cut, but the invented values still failed. Rejected.
- **Anthropic's native Messages API with structured outputs:** needs the `anthropic` SDK (not a dependency), a new adapter path and the same schema subset, so the recursion would have to be unrolled anyway. A larger change for the same schema.
- **Flattening the schema of the planner for every provider:** changes the prompts, the domain mapping and the golden file, and takes the depth limit away from the providers that do not need it.
