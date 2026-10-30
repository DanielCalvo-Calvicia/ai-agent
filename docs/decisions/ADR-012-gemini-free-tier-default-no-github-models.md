# ADR-012 — GitHub Models is retired: Google models on the free tier are the default

**Status:** Accepted (2026-10-28, the maintainer's answers of 2026-10-27 in [PR-004](../proposals/PR-004-model-catalog-gemini-free-tier.md) section 8, recorded in [T-02.1](../tasks/T-02_model-catalog-refresh/T-02.1_decisions.md)). Built in T-02; not yet run end to end with a real model (T-02.10), and the Gemini ids were not re-checked with the real key (T-02.3).

## Context

The `DEFAULT_MODEL` of all 12 phases was a GitHub Models id (`gpt-4.1`, `gpt-4.1-mini`), free and needing only a GitHub token. GitHub retired GitHub Models on 2026-07-30 (playground, catalog, inference API and bring-your-own-key). The service worked only because `config/step_models.json` named a profile; with no profile the agent had no usable model. The catalog also held ids that no provider lists any more, and `gpt-4.1-mini` and `gpt-4.1-nano`, priced as OpenAI's, were routed to GitHub because they existed only there.

GitHub names Azure AI Foundry and GitHub Copilot as replacements. Foundry is a paid Azure service that needs an Azure resource, a model deployment and its own endpoint and key; it does not take a GitHub token. Nothing replaces both properties of GitHub Models (free, one token).

## Decision

1. **GitHub Models is gone from the service.** `GithubModels`, `is_github`, the provider route, `github_api_key`, `github_url` and the variables `GITHUB_PAT`, `GITHUB_API_KEY` and `GITHUB_URL` are removed; they are no longer read.
2. **The code default is a Google model with a free tier.** `gemini-3.1-flash-lite` for triage, data engineer, answer checker, clarification and emotion reader; `gemini-3.8-flash` for project manager, safety gate, cognitive worker, MCP operator, draft writer, editor in chief and motion planner. Both have a free tier on Google's pricing page of 2026-10-27, so the agent runs and is tested with no billing.
3. **The active profile is `google_free`** (the same two models, in `config/step_models.json`). `budget50_groq` and the others stay defined, not active.
4. **The catalog lists only ids found, with their status, in the provider's own documentation of 2026-10-27.** An id without full information (id, price or status) is not used: a comment in `model_catalog.py`, and `_disabled` in a JSON price file (the loaders read only `models`). `MistralModels` is an empty enum because Mistral's pages give no confirmed API id; the route and keys stay so a verified id can be added. Models that are deprecated but still served keep a comment with their shutdown date.
5. **Dated prices are not built.** The doubling of `gemini-3.8-flash` and `gemini-3.6-flash` on 2027-01-01 and of `gemini-4-argon` on 2026-12-01 stays text in `price_note` (a known gap).
6. **Google is the free testing provider.**

## Consequences

- Positive: a clean start with no billing and one key (`GOOGLE_API_KEY`) plus `GOOGLE_URL`; the catalog, the price files, the generated tables and the tests agree; the suite passes (893 tests on 2026-10-28).
- Negative: Google says free-tier content is used to improve its products, and the agent sends the user's text and, in the special flow, Business Central answers to the provider (see [security](../security/security.md)); the free-tier rate limits are not published on Google's pricing page and are untested; at paid prices `google_free` costs about $0.20 per big-plan message (about 175 EUR per 1,000 messages, against the 50 EUR budget); the price of `gemini-3.8-flash` doubles on 2027-01-01; `gemini-2.5-*` is served only to users who used it before, so the profiles that use it may fail for a new key.
- Open until T-02.3 and T-02.10: whether every Gemini id answers with the real key, `gemini-4-argon` and `gemini-3-flash-preview` (in the catalog, not yet in `config/gemini_models.json`), the real token use and the thinking tokens of `google_free`.
- A lookup detail found by the suite: calling an empty enum raises `TypeError` on Python 3.14, so `get_selected_model` continues on `ValueError` and `TypeError`.

## Alternatives not taken

- **Azure AI Foundry:** paid, no GitHub token, a deployment per model and a different endpoint: a code change, not a token swap. Not free.
- **A billed Google key as the default:** it avoids the free-tier terms but costs about 175 EUR per 1,000 big-plan messages for `google_free`. Available any time by billing the key; the code does not change.
- **Groq (`budget50_groq`) as the default:** free plan, but its limits were not confirmed and it needs a second key; it stays a profile.
- **Keeping a GitHub id as the code default:** it would fail on the first message without a profile.
- **Building a dated price schedule now:** deferred by the owner.

*Dated note 2026-10-28:* the real check of T-02.3 showed that `gemini-2.5-flash` and `gemini-2.5-flash-lite` answer 404 ("no longer available to new users") with the project's key. They were removed from the catalog, the price file and the profiles `proven`, `budget`, `budget50` and `budget50_groq`, which now use `gemini-3.1-flash-lite` and `gemini-3.5-flash-lite`. `gemini-3.8-flash`, a default, answered 503 "high demand" on every attempt that day; it is kept (a capacity problem, not an unknown id) and is to be retried.

*Dated note 2026-10-28 (second):* `gemini-3.8-flash` did not answer on any try of that day (no answer in 60 s, a raw request got 503 "high demand"). The seven phases that had it as their default now use `gemini-3.6-flash`, which answered in 3 s at the same price, in the code defaults and in the profile `google_free`; `gemini-3.1-flash-lite` for the five small steps is unchanged. The profiles `balanced` and `quality` still name `gemini-3.8-flash`. Move the defaults back when `gemini-3.8-flash` answers (rated "best" for planning, against "good" for `gemini-3.6-flash`).

*Dated note 2026-10-28 (third):* a first measurement of the free-tier limits with this project's key: `gemini-3.1-flash-lite` answered 10 calls in a row, `gemini-3.6-flash` answered 7 in about 30 s and then returned 429 "quota exceeded" (and answered again 25 s later). Since the seven flash phases use the second model, one message with a plan can reach the limit on the free tier; the profile `proven` (every step on `gemini-3.1-flash-lite`), a billed key or pacing the calls are the ways out. Not decided yet.

*Dated note 2026-10-28 (fourth):* the active profile is now `proven` (every step on `gemini-3.1-flash-lite`), not `google_free`, because of the free-tier limit measured the same day. Decision 3 above is superseded for the choice of the active profile; `google_free` stays defined (the code defaults still match it). `proven` costs about 38 EUR per 1,000 big-plan messages at paid prices and fits the 50 EUR budget. To go back, set `profile` to `google_free` in `config/step_models.json`.

*Dated note 2026-10-28 (fifth):* `gemini-3-flash-preview` (it answered a test call) and `gemini-4-argon` (not called: no free tier) entered `config/gemini_models.json`, the second with `api_check` "not called" and ratings that are estimates; the tables mark it as untested.

*Dated note 2026-10-28 (sixth):* a second free-tier limit was found: Google answered 429 "Generate content requests per day limit exceeded on Free Tier, limit: 20" for `gemini-3-flash-preview` (per project and model; the answer asks to retry in about 16 hours), after about 20 calls of the day. At one message of 4 to 8 calls, a free key allows only a few messages a day on a model, whichever profile is active. This weakens the case for the free tier as the default for anything but short tests; a billed key, other providers (`budget50_groq` needs a Groq key) or spreading the calls over models are the options. Not decided.

*Dated note 2026-10-28 (later):* the open points above are closed by scope, not by result: at the maintainer's request T-02.3 and T-02.10 use the Anthropic models (the only paid key at hand). The paid-only Google ids (`gemini-4-argon`, `gemini-3.1-pro-preview`) stay in the catalog unchecked, `gemini-3.8-flash` was last seen answering 503, and the token and thinking numbers of the Google profiles were not re-measured.
