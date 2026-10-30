# T-02 — Model catalog refresh: no GitHub Models, Google free tier by default

| | |
|---|---|
| Status | done (created 2026-10-27; T-02.1, T-02.2 and T-02.4 to T-02.9 done on 2026-10-28; T-02.3 and T-02.10 done on 2026-10-28 with the Anthropic models; closed by the maintainer on 2026-10-30) |
| Kind | epic |
| Parent | project |
| Depends on | — (it shares files with T-01, which is not committed: see Open points) |
| Blocks | T-01.9 (the first real run should use the models this epic leaves in place) |

> Source: [PR-004](../../proposals/PR-004-model-catalog-gemini-free-tier.md), a read-only review of the code and of each provider's public documentation on 2026-10-27. Its section 8 holds the owner's decisions; this epic does not reopen them.

## Goal

The model catalog lists only models that exist, GitHub Models is gone from the service, and every phase falls back to a Google model with a free tier. Every file that depends on the catalog (prices, ratings, tokens, cost tables, tests, documents) is true again.

## What exists and what changes

| Today | After T-02 |
|---|---|
| The code default of all 12 phases is a GitHub Models id (`GPT_4_1`, `GPT_4_1_MINI`); GitHub Models was retired on 2026-07-30 (F14) | A Google model with a free tier: `gemini-3.1-flash-lite` or `gemini-3.8-flash` (F17) |
| The active profile is `budget50_groq` (needs a Groq key) | `proven` (every step on `gemini-3.1-flash-lite`); `google_free` was built in T-02.2 and active until 2026-10-28, when the free-tier limit of `gemini-3.6-flash` made `proven` the choice |
| The catalog holds `GithubModels`, `MistralModels` and ids that no provider lists any more | Only models found, with their status, in the provider's documentation; the rest are comments |
| `gpt-4.1-mini` and `gpt-4.1-nano` are priced as "openai" but exist only in `GithubModels`, so they route to GitHub (F15) | Removed |
| Ten priced ids are not in the catalog and cannot be chosen (F16) | Five enter the catalog (id, price and status confirmed); five (Mistral, DeepSeek) are `_disabled` in the JSON price file |
| Ratings and tokens come from `gemini-2.5-flash` and `gemini-3.8-flash` runs | Re-measured with the new defaults (T-02.10) |
| `docs/models/*` say `budget50_groq` is active | Regenerated |
| The price changes of 2026-12-01 and 2027-01-01 are only text in `price_note` | A known gap in `requirements.md` (decision 4) |

## Subtasks

| Order | Task | Kind | Status |
|---|---|---|---|
| 1 | [T-02.1 Decisions](T-02.1_decisions.md) | decision | done (2026-10-27) |
| 2 | [T-02.2 Profile `google_free`](T-02.2_profile-google-free.md) | code | done (2026-10-28) |
| 3 | [T-02.3 Confirm the ids with the real key](T-02.3_confirm-ids.md) | manual | done (2026-10-28; Anthropic ids checked instead of the paid-only Google ids) |
| 4 | [T-02.4 Catalog](T-02.4_catalog.md) | code | done (2026-10-28) |
| 5 | [T-02.5 Defaults and routing](T-02.5_defaults-and-routing.md) | code | done (2026-10-28) |
| 6 | [T-02.6 Prices, ratings and token files](T-02.6_prices-ratings-tokens.md) | code | done (2026-10-28) |
| 7 | [T-02.7 Tests and golden file](T-02.7_tests-and-golden.md) | test | done (2026-10-28) |
| 8 | [T-02.8 Generated documents](T-02.8_generated-documents.md) | docs | done (2026-10-28) |
| 9 | [T-02.9 Documentation and ADR](T-02.9_documentation.md) | docs | done (2026-10-28) |
| 10 | [T-02.10 First real run (on Claude)](T-02.10_first-real-run.md) | manual | done (2026-10-28; the maintainer closes the epic) |

T-02.4 to T-02.6 leave the suite red until T-02.7 ends; do them in one sitting.

## Exit criteria

`GithubModels`, `GITHUB_PAT`, `GITHUB_URL`, `github_api_key`, `is_github` and `gpt-4.1` appear nowhere outside history documents (`docs/proposals`, `docs/reference`, the ADRs, the questionnaires), the task files and the tests that check they are gone; every id in `model_catalog.py` was found, with its status, in the provider's documentation; every other id is a comment; `tests/manual/show_models.py` prints a model and a price for every step, with no `?`; with only `GOOGLE_API_KEY` and `GOOGLE_URL` set, `GET /available` is true and the agent starts with `google_free`; `docs/models/*` name `google_free` as active; the whole suite passes; every document of the table in `CLAUDE.md` is true; the maintainer has run T-02.10 and closed the epic.

## Rules that bind every task of this epic

- Dependencies go one way: `domain/` imports nothing of the application; `application/` never imports `infrastructure/`; the LLM adapter stays behind `LLMOutboundPort`.
- Never edit a generated file by hand (`docs/models/*`, the schema tree).
- An id without full information (id, price and status) is not used: a comment in Python, `_disabled` in a JSON price file (decision 6).
- Nothing calls a real LLM or a real provider API except T-02.3 and T-02.10, and only after the maintainer says so: it costs money.
- Never read, print or copy a `.env` value.
- Prices are not made dated in this epic (decision 4).
- A change to a prompt, schema, model or message format changes `tests/golden/flow_golden.json`: read the diff, then regenerate on purpose.
- Commit and push only when asked.
- The baseline of the [tasks README](../README.md) section 3.

## Open points

- **Files shared with T-01.** T-01 changed, and has not committed, `domain/value_objects/llm_request/model_catalog.py` (`claude-sonnet-5`), `config/step_models.json` (profile `claude_sonnet`), `.env.example`, several documents and `tests/golden/flow_golden.json`. Do this epic on the same branch (`feature_dynamics_mcp`) after T-01's work is committed, or ask the maintainer where it goes; two branches must not edit the same files.
- **`claude-sonnet-5`** is a legacy id (still available). T-01.3 chose it; moving the `claude_sonnet` profile to `claude-sonnet-5-5` belongs to T-01.9, not here.
- **Free tier.** Google says free-tier content is used to improve its products, and its rate limits are not on the pricing page. Both go into `security.md` and `requirements.md` (T-02.9); the limits are checked at T-02.10.
- **OpenAI adapter.** GPT-5 models reject `max_tokens`; whether GPT-6 and GPT-5.6 do too is unknown. None is a default; a model that needs an adapter change stays `needs adapter change`.
- **Not decided here:** a dated price schedule (decision 4), and the real ids of the current Mistral models.

## Closing note (2026-10-30)

Closed by the maintainer. Two exit criteria above were overtaken by the maintainer's own later decisions and are met in their new form, not in the written one:

- "the agent starts with `google_free`" and "`docs/models/*` name `google_free` as active": the active profile has been `proven` (every step on `gemini-3.1-flash-lite`) since 2026-10-28, after the free-tier probe (ADR-012, fourth dated note). `google_free` stays defined and tested.
- "every id in `model_catalog.py` was found in the provider's documentation": `gemini-3.8-flash` kept answering 503 "high demand" and is not used by any profile; the paid-only ids (`gemini-4-argon`, `gemini-3.1-pro-preview`) were not called (T-02.3, changed scope).

The "appears nowhere" criterion for the GitHub names also holds for tracked files: nine stale `__pycache__` files, two of them still holding `GithubModels` and `gpt-4.1`, were removed from git and the folder is ignored.

Not scheduled (recorded in T-02.3, T-02.10 and ADR-012): a retry of `gemini-3.8-flash`, the run on `proven`, the token numbers of the Google profiles, the paid-only Google ids.
