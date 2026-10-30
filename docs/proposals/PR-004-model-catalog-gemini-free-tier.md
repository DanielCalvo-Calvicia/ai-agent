# Model catalog refresh: drop GitHub Models, Gemini (free tier) as the code default

Status: **IMPLEMENTED 2026-10-28 in epic [T-02](../tasks/T-02_model-catalog-refresh/T-02_model-catalog-refresh.md)** (decisions answered 2026-10-27, section 8; the decision is recorded in [ADR-012](../decisions/ADR-012-gemini-free-tier-default-no-github-models.md)). This is history: the text below is the plan as written on 2026-10-27, from a read-only review of the code and of each provider's public documentation on that date.
Dated note 2026-10-28: the file was renamed from `PR-004-model-catalog-paid-gemini.md` (the first idea was a paid Gemini key; the owner chose the free tier). Where the work differs from this plan: `MistralModels` stays as an empty enum (the provider route and keys stay); `gemini-4-argon` and `gemini-3-flash-preview` are in the catalog but not yet in `config/gemini_models.json` (they need the `api_check` of T-02.3); five of the ten priced ids that were not in the catalog entered it and five (Mistral, DeepSeek) are in `_disabled`; the dated prices are a known gap; the suite found a bug in the first version of the lookup (an empty enum raises `TypeError` on Python 3.14), fixed in T-02.4.

## 1. Goal

1. Make `domain/value_objects/llm_request/model_catalog.py` list only models that exist today. Every unavailable id is removed.
2. Stop using GitHub Models (retired) as the code default, and remove it from the service.
3. Make Gemini models that have a free tier the code default of every phase (no billing needed to run or test the agent).
4. Bring every file that depends on the catalog (prices, ratings, tokens, cost tables, tests, docs) back in line, in the same piece of work (`CLAUDE.md`, "every change updates the documentation").

## 2. Why

- GitHub Models is **retired**: GitHub's own article gives 30 July 2026 as the date (playground, catalog, inference API and bring-your-own-key). The code default of 8 phases is still a GitHub id (`GithubModels.GPT_4_1`, `GPT_4_1_MINI`). Today it only works because `config/step_models.json` sets a profile; clear the profile and the agent has no working model.
- GitHub Models needed only a GitHub token and was free. **Nothing replaces both properties**:
  - Azure AI Foundry (named by GitHub as the replacement) is a paid Azure service. No official free tier was found. It does not take a GitHub token: it needs an Azure resource, a model deployment and its own endpoint and key, and calls address the deployment name. Moving to it is a code change, not a token swap. Not verified: whether a new Azure account gets free credit.
  - GitHub Copilot is a separate product, not an inference API for this agent.
- For testing, the free options are Google AI Studio (free tier on the Flash and Flash-Lite models; the free tier uses content to improve Google's products), Groq (free plan, limits not confirmed), Mistral (free plan with phone check; Experiment-plan requests may be used for training) and Ollama (local). Cohere's trial key (1,000 calls a month, 20 per minute) is too small for this pipeline.
- The owner chose the **Google free tier** for the defaults and for testing (section 8). Two consequences to keep in view: Google says free-tier content is used to improve its products (a billed key is not), and the free tier has rate limits that Google's pricing page does not state. The agent sends the user's speech, and in the special flow Business Central answers, to the provider; `docs/security/security.md` must say that plainly.

## 3. What was found

### 3.1 Models that no longer exist or are not listed (to remove)

| Provider | Remove | Evidence |
|---|---|---|
| GitHub | the whole `GithubModels` enum and its provider | GitHub Models retired 2026-07-30 |
| Anthropic | `claude-4-6-opus-latest`, `claude-4-6-sonnet-latest`, `claude-4-5-sonnet-latest`, `claude-3-7-sonnet-latest`, `claude-3-5-sonnet-latest`, `claude-3-5-haiku-latest` | not in the models overview (the current ids have no `-latest`) |
| Google | `gemini-3.7-flash`, `gemini-3.5-flash`, `gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-2.5-pro` | not on Google's models or pricing page; `gemini-2.5-pro` also failed this project's own `api_check` (404, "no longer available to new users") |
| Groq | `llama4-70b-preview`, `llama4-8b-preview`, `llama-3.1-405b-reasoning`, `mixtral-8x7b-32768` | not in Groq's model list |
| Cohere | `command-r`, `command-r-plus` (deprecated 2025-09-15), `command-r7` (the id is `command-r7b-12-2024`) | Cohere's models page |
| Mistral | `mistral-large-2411` (retired 2026-05-31) | Mistral's deprecation table |
| OpenAI | `gpt-5-turbo` (never listed), `gpt-4.5`, `gpt-4-turbo`, `o1`, `o1-mini` | OpenAI's deprecations page: `o1` and `gpt-4-turbo` shut down 2026-10-23, `o1-mini` and `gpt-4.5-preview` earlier; `gpt-4.1-nano` also shut down 2026-10-23 (it only exists in `GithubModels`) |
| Mistral | every Mistral id of the catalog | decision 2: the current models have no confirmed API id or price (3.3), so they are removed |

### 3.2 Current ids found

| Provider | Current ids |
|---|---|
| Anthropic | `claude-fable-5-1`, `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`. Legacy but available: `claude-sonnet-5`, `claude-opus-5`, `claude-opus-4-8`, `claude-opus-4-7`, `claude-opus-4-6`, `claude-opus-4-5`, `claude-sonnet-4-6`, `claude-haiku-4-5` |
| Google | stable: `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-4-argon`; preview: `gemini-3-flash-preview`, `gemini-3.1-pro-preview`; `gemini-2.5-*` served "until further notice" but only to users who used them before |
| Groq | production: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`; preview: `qwen/qwen3.8-27b`, `minimaxai/minimax-m2.7` |
| Cohere | `command-a-plus-05-2026`, `command-a-03-2025`, `command-a-reasoning-08-2025`, `command-a-vision-07-2025`, `command-r-08-2024`, `command-r-plus-08-2024` |
| OpenAI (id, price and status all on OpenAI's pricing and deprecations pages) | shut down on a date already passed: remove. Deprecated with a date still ahead, keep and comment the date: `gpt-5`, `gpt-5-mini`, `gpt-5-nano` (2026-12-11), `gpt-4o` (2027-01-14), `gpt-5.4-nano` (2027-04-01). Not deprecated: `gpt-6-astra`, `gpt-6.1-sol`, `gpt-6.1-terra`, `gpt-6-luna`, `gpt-6-sol`, `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.2`, `o3-mini`. Prices (input / output): `gpt-6-luna` 0.10 / 0.50, `gpt-6.1-terra` 1.00 / 5.00, `gpt-6.1-sol` 2.00 / 10.00, `gpt-5.6-luna` 0.20 / 1.20, `gpt-5.6-terra` 2.00 / 12.00, `gpt-5.4-mini` 0.75 / 4.50 |
| Ollama | `llama4`, `llama3.3`, `phi4`, `deepseek-v3`, `mistral-nemo` all exist in the Ollama library and none is marked deprecated (the page shows sizes but not full tags, and all were last updated about a year ago) |

### 3.3 Not confirmed (do not guess)

- **OpenAI:** resolved by a second search (3.2). The models page alone lists only the GPT-6 family, but the pricing and deprecations pages give id, price and status for the rest. Not known: whether the GPT-6 and GPT-5.6 models accept the parameters the agent sends (the GPT-5 models reject `max_tokens` and need `max_completion_tokens`, as `other_models.json` already notes), so none of them is a default.
- **Mistral:** not resolved. Docs and pricing pages name the models (Large 4, Medium 3.5, Small 4, Ministral 3, Codestral) and give documentation slugs such as `mistral-small-4-0-26-03`, but no confirmed API id and no price. By the owner's rule (decision 2) they leave the catalog, and the three Mistral entries of `other_models.json` and the slug-style ids in it are commented out (decision 6).
- **Ollama:** the names exist; there is no price (local). Kept.

### 3.4 Paid Gemini prices (USD per 1M tokens, standard paid tier, read 2026-10-27)

| Model | Input | Output (with thinking) | Note |
|---|---|---|---|
| `gemini-3.1-flash-lite` | 0.25 | 1.50 | |
| `gemini-3.5-flash-lite` | 0.30 | 2.50 | |
| `gemini-3-flash-preview` | 0.50 | 3.00 | preview |
| `gemini-3.8-flash`, `gemini-3.6-flash` | 0.75 | 3.75 | **double on 2027-01-01** (1.50 / 7.50) |
| `gemini-3.1-pro-preview` | 2.00 (4.00 above 200k) | 12.00 (18.00 above 200k) | preview |
| `gemini-4-argon` | 2.00 | 10.00 | **double on 2026-12-01** (4.00 / 20.00); no free tier |
| `gemini-2.5-flash-lite` / `2.5-flash` | 0.10 / 0.30 | 0.40 / 2.50 | limited availability |

Every price already in `config/gemini_models.json` matches this table; the file needs removals and additions, not price corrections.

### 3.5 Problems in the repository found by the review

1. `gpt-4.1-mini` and `gpt-4.1-nano` are priced in `config/other_models.json` as provider "openai", but they exist only in `GithubModels`, so the code routes them to GitHub. They break with it.
2. Ten priced ids are not in the catalog and so cannot be chosen: `claude-haiku-4-5`, `gpt-5-nano`, `gpt-5.4-mini`, `gpt-5.6-luna`, `gpt-5.6-terra`, `mistral-small-4-0-26-03`, `ministral-3-14b-25-12`, `mistral-large-3-25-12`, `deepseek-flash`, `deepseek-v4-pro` (the DeepSeek provider has no enum at all).
3. The ratings, `step_tokens` and `measured_runs.json` were measured with `gemini-2.5-flash` and `gemini-3.8-flash`. The new defaults have no measurement yet.
4. `infrastructure/outbound/usage/prices.py` holds one price per model. The price changes on 2026-12-01 and 2027-01-01 exist only as text in `price_note`, so cost figures become wrong after those dates.
5. `.env` is not in this checkout, so `api_check` (one tiny call per id) could not be re-run during the review.

## 4. Proposed code defaults

| Phases | Default | Why |
|---|---|---|
| 1 triage, 6 data engineer, 9 answer checker, 99 clarification, expression emotion reader | `gemini-3.1-flash-lite` | rated "best" for these steps, measured 0 thinking tokens, cheapest paid current model |
| 2 project manager, 3 safety gate, 4 cognitive worker, 5 MCP operator, 7 draft writer, 8 editor in chief, 20 motion planner | `gemini-3.8-flash` | newest Flash, rated "best" for planning, worker, tools and writing; **price doubles on 2027-01-01** |

Both models have a free tier (Google's pricing page, read 2026-10-27), so the defaults need no billing. The paid prices in 3.4 apply only if the key is billed. Not used as defaults: `gemini-3.1-pro-preview` and `gemini-4-argon` (no free tier), `gemini-2.5-*` (limited to users who used them before).

The code default is only the last fallback. The profile in `config/step_models.json` wins (decision 3).

## 5. Scope: files and how each changes

| Area | File | Change |
|---|---|---|
| Catalog | `domain/value_objects/llm_request/model_catalog.py` | delete `GithubModels` and its entries in `ModelIdList` and `SupportedModel`; remove the ids of 3.1; add the current ids of 3.2 (and `gemini-4-argon`); OpenAI per 3.2 (shutdown dates as comments); delete `MistralModels`; keep the Ollama names; ids without full information stay as comments (decision 6) |
| Catalog | `domain/value_objects/llm_request/model.py` | remove the `GithubModels` re-export and `is_github` |
| Defaults | `application/orchestration/phases/**` (triage, project_manager, safety_gate, cognitive_worker, mcp_operator, data_engineer, motion_planner, emotion_reader), `phases/phase.py`, `phases/catalog.py` | `DEFAULT_MODEL` from section 4; retype `GithubModels` to `GoogleModels` |
| Defaults | `application/orchestration/support/model_selection.py` | retype; fix the provider-order docstring |
| Routing | `infrastructure/outbound/llm/provider_models.py`, `config.py`, `vercel.py` | remove the GitHub route, `github_api_key`, `github_url` and the GitHub check of `/available` |
| Choice | `config/step_models.json` | check every profile id exists; mark or replace the `gemini-2.5-*` profiles (`proven`, `budget`, `budget50`); decide the active profile; the `claude_sonnet` profile uses a legacy id |
| Prices, ratings | `config/gemini_models.json` | remove `2.5-pro`, `3.7-flash`, `3.5-flash`; add `gemini-4-argon` (`free_tier: false`, price note for 2026-12-01) and `gemini-3-flash-preview`; refresh `_source`, dates, `api_check` and ratings |
| Prices, ratings | `config/other_models.json` | remove `gpt-4.1-*`; update the Anthropic entries to the 5.5 ids and prices (Fable 5.1 10/50, Opus 5.5 4/20, Sonnet 5.5 2/10, Haiku 5.5 from 0.10/0.50); prune or flag the ten ids of 3.5 item 2 |
| Tokens | `config/measured_runs.json`, `step_tokens` | re-measure with the new defaults (real run, costs money, ask first); until then label the old numbers as measured with `gemini-2.5-flash` |
| Cost | `tests/cost_estimate.py` | update `THINKING_FACTOR` (drop removed ids, add `gemini-4-argon`); revisit the comparison rows |
| Cost | `infrastructure/outbound/usage/prices.py` (+ generators) | no change (decision 4); confirm they ignore a `_disabled` list (decision 6) |
| Gap | `docs/requirements/requirements.md` | add the dated-price gap (decision 4) and the free-tier terms and rate limits |
| Generated | `docs/models/gemini_models_per_step.md`, `models_per_step_budget.md`, `cost_of_a_full_plan.md` | regenerate (`show_models.py --write`, `--budget`, `estimate_cost.py --write`); never edit by hand |
| Tests | `test_model_config`, `test_agent_behavior`, `test_units`, `test_motion_flow`, `test_flow_objects`, `test_cost_estimate`, `tests/manual/mcp_direct.py` | replace `GithubModels.GPT_4_1` and the `gpt-4.1` expectations; rewrite the GitHub route tests; check `test_model_config.py` lines 209 to 252 (every shipped id is in the catalog once) |
| Tests | `tests/golden/flow_golden.json` | regenerate on purpose with `UPDATE_GOLDEN=1`, after reading the diff |
| Docs | `README.md`, `CLAUDE.md` (Config section), `.env.example` (lines 11, 25, 48, 52), `docs/configuration/environment-variables.md`, `docs/architecture/architecture.md`, `docs/security/security.md`, `docs/README.md`, `docs/requirements/requirements.md` | remove `GITHUB_PAT` / `GITHUB_URL`; correct every line that calls a GitHub id the code default; keep what is planned marked as planned |
| Docs (history) | `docs/reference/github-models.md`, `model-catalog-notes.md`, `model-recommended-per-phase.md` | already carry "retired / unmeasured" banners; add a dated note, do not rewrite |
| Records | `docs/decisions/ADR-011-...`, `docs/tasks/` (task file, `README.md` board, `ORDER.md`) | new ADR: GitHub Models retired, defaults moved to paid Gemini, dated price changes; a task file for the work |

## 6. Order of work

1. Decide section 8. Re-run `api_check` with the real key where `.env` exists, and fix the id lists first.
2. Catalog and `model.py`; phase defaults and types; routing and config removal. The tests fail until step 3.
3. Tests and golden file (read the golden diff before regenerating).
4. Price and rating files; `cost_estimate.py`.
5. Regenerate the three `docs/models` files.
6. Written docs, `.env.example`, `CLAUDE.md`, ADR, task board.
7. One real measured run with the new defaults (ask first, it costs money); update `measured_runs.json` and `step_tokens`; regenerate the tables again.

## 7. Verification

- `pytest tests` (about 640 tests, mock-based). The `windows` virtual environment is not in this checkout: it has to be rebuilt or the tests run where it exists. Not run during the review.
- `scripts/split_schemas.py` still passes (no schema change expected).
- `tests/manual/show_models.py` prints a model and a price for every step, with no `?`.
- `GET /available` is true with only `GOOGLE_API_KEY` and `GOOGLE_URL` set.
- Search of the repository finds no `GithubModels`, `GITHUB_PAT`, `GITHUB_URL` or `gpt-4.1` outside the history documents.

## 8. Decisions (owner, 2026-10-27)

| # | Question | Answer | What it means for the work |
|---|---|---|---|
| 1 | Which Gemini models are the default? | The Google models, on the **free tier** (after seeing the paid prices and the free-tier terms). | Section 4 stands: `gemini-3.1-flash-lite` and `gemini-3.8-flash`, both with a free tier. `gemini-3.1-pro-preview` and `gemini-4-argon` stay in the catalog and price file but are not defaults. Document the free-tier terms in `docs/security/security.md`. Test the free-tier rate limits (not stated by Google) before relying on them. |
| 2 | Mistral, OpenAI, Ollama ids | Search them; when the information is missing or partial, delete them. | Searched (3.2, 3.3). OpenAI: complete, kept as listed. Ollama: names exist, kept. Mistral: partial, **deleted**. |
| 3 | Active profile | Asked what it means. | `config/step_models.json` has a key `profile` naming the active set of per-step models (today `budget50_groq`: Groq `openai/gpt-oss-120b` for five steps, Google lite models for the rest). The profile wins over the code default, so changing the code default alone changes nothing while a profile is active. **Answered the same day: a Google-only profile, now active.** `google_free` was added to `config/step_models.json` and set as `profile` on 2026-10-27; `budget50_groq` stays defined, not active. Work continues in epic [T-02](../tasks/T-02_model-catalog-refresh/T-02_model-catalog-refresh.md). |
| 4 | Dated prices | Not for now. | A known gap in `docs/requirements/requirements.md`: cost figures are wrong after 2026-12-01 (`gemini-4-argon`) and 2027-01-01 (`gemini-3.8-flash`, `gemini-3.6-flash`). Does not touch `prices.py`. |
| 5 | Free testing provider | The Google ones. | Tests and manual runs use the Google free tier. GitHub, Groq and Ollama are not the test path. |
| 6 | Priced models that are not in the catalog | Without all the information they are not used: comment them. | Python: the id stays in the enum as a comment with the reason. JSON price files cannot hold comments, so the entry moves to a `_disabled` list that `prices.py` and the generators ignore (they read only `models`). Applies to the ten ids of 3.5 item 2, to the Mistral entries and to the slug-style Mistral ids. |

Nothing is open. The work is epic [T-02](../tasks/T-02_model-catalog-refresh/T-02_model-catalog-refresh.md).

## Sources (read 2026-10-27)

- GitHub Models retirement: https://docs.github.com/en/github-models
- Microsoft Foundry overview: https://learn.microsoft.com/en-us/azure/ai-foundry/what-is-azure-ai-foundry
- Gemini models and pricing: https://ai.google.dev/gemini-api/docs/models and https://ai.google.dev/gemini-api/docs/pricing
- Claude models overview: https://platform.claude.com/docs/en/about-claude/models/overview
- Groq models: https://console.groq.com/docs/models
- Cohere models and rate limits: https://docs.cohere.com/docs/models and https://docs.cohere.com/docs/rate-limits
- Mistral models: https://docs.mistral.ai/getting-started/models/models_overview/
- OpenAI models: https://developers.openai.com/api/docs/models
- Mistral free plan (help article and secondary sources, limits unverified): https://help.mistral.ai/en/articles/450104-how-can-i-try-the-api-for-free-with-the-experiment-plan

Dated note 2026-10-28: the active profile became `proven` (every step on `gemini-3.1-flash-lite`), see [ADR-012](../decisions/ADR-012-gemini-free-tier-default-no-github-models.md). The tables above describe the plan of 2026-10-27.
