# Models for each step, within a budget

_Generated from `config/gemini_models.json`, `config/other_models.json`, `config/measured_runs.json` and `config/budget.json` by `tests/manual/show_models.py --budget`. Edit those files, not this one._

## The budget

- **50 EUR a month at most, for 1,000 messages** = 0.050 EUR = **$0.0575 per message** (ECB euro reference exchange rate (1 EUR = 1.1490 USD on 2026-09-21; it moved between 1.146 and 1.170 in the last 30 days)).
- The worst case is used: **every message has a big plan of 30 actions** (5 actions with 5 subactions each, 5 of them with a tool). A message with a small plan of 2 actions costs far less, so the real month will be under the budget.
- Prices and status: Google's pages ai.google.dev/gemini-api/docs/pricing, /models and /thinking, read on 2026-09-21; the prices and the list of models were checked again on 2026-10-27 (T-02.6). Prices are USD per 1M tokens, text, standard paid tier, and the output price includes thinking tokens. Check the page before you rely on a number.
- Prices: OpenAI developers.openai.com/api/docs/pricing, Anthropic platform.claude.com/docs/en/about-claude/pricing, mistral.ai/pricing/api, DeepSeek api-docs.deepseek.com/quick_start/pricing and Groq console.groq.com/docs/models, read on 2026-09-21 through a page summariser. USD per 1M tokens, standard tier. Check them before you rely on a number. The Gemini models are in gemini_models.json. OpenAI prices and shutdown dates re-read on 2026-10-27 (developers.openai.com/api/docs/pricing and /deprecations); claude-sonnet-5-5 from platform.claude.com on the same day (T-02.6).
- The ratings are estimates from the size and description of each model, NOT measurements. Only the models marked tested were run here. Ratings: **best** = the right model for this step; **good** = works well, a fair price for the job; **ok** = works, but slower, weaker or more expensive than needed; **weak** = likely to fail or to give poor results here; **avoid** = wasteful (too expensive or too slow for what the step does).

## 1. What was measured, and what it changes

One real message was sent through the whole agent with each model on every step ("Compare Python, Go and Rust. For each language give two strengths and two weaknesses, then recommend one for a beginner and explain why."). Tokens as the provider counted them; **thinking = total - sent - answered**.

| Model | Calls | Sent | Answered | Thinking | Cost of that message | Per 1,000 such messages |
|---|---|---|---|---|---|---|
| `openai/gpt-oss-20b` | 6 | 10,161 | 4,300 | 0 | $0.0021 | $2.05 = 1.79 EUR |
| `openai/gpt-oss-120b` | 6 | 10,393 | 3,885 | 0 | $0.0039 | $3.89 = 3.39 EUR |
| `gemini-3.1-flash-lite` | 7 | 8,938 | 1,487 | 0 | $0.0045 | $4.46 = 3.89 EUR |
| `gemini-3.8-flash` | 7 | 9,757 | 2,357 | 3,611 | $0.030 | $29.70 = 25.85 EUR |

- **Thinking is billed, and the API hides it.** `gemini-2.5-flash` thought 2,484 tokens for 3,194 answered (44% more output) and `gemini-3.8-flash` 3,611 for 2,357 (150% more). Google's `completion_tokens` does not include them; only `total_tokens` does. The two lite models thought nothing. This is why the Flash models cost 4 to 14 times more than the lite ones on the same message.
- `openai/gpt-oss` (Groq) is a reasoning model too, but its reasoning is inside the counted output tokens (about 2.5 times the visible answer, measured), and its price is low: it cost about the same as the lite models.
- A switch exists to turn thinking off: with `reasoning_effort="none"` `gemini-2.5-flash` thought 0 tokens instead of 411 on a test question (tested with a direct call). The agent does not send it yet, so a thinking model is still billed for thinking.

## 2. Profiles and their cost

Cost of one message, thinking included. The limit is **$0.0575 (0.050 EUR)**. Big plan = 30 actions; small plan = 2 actions.

| Profile | Big plan, USD | Big plan, EUR per 1,000 messages | Fits the budget? | Small plan, USD | Providers | Active |
|---|---|---|---|---|---|---|
| strongest (per step, from the earlier table) | $0.350 | 304.37 | no | $0.055 | Anthropic, Google, OpenAI |  |
| proven | $0.044 | 37.90 | **yes** | $0.0069 | Google | yes |
| budget | $0.050 | 43.45 | **yes** | $0.0078 | Google |  |
| balanced | $0.104 | 90.28 | no | $0.021 | Google |  |
| quality | $0.260 | 225.91 | no | $0.066 | Google |  |
| budget50 | $0.048 | 41.38 | **yes** | $0.0078 | Google |  |
| claude_sonnet | $0.316 | 275.00 | no | $0.050 | Anthropic |  |
| budget50_groq | $0.038 | 32.76 | **yes** | $0.0060 | Google, Groq |  |
| google_free | $0.201 | 174.89 | no | $0.033 | Google |  |
| claude_haiku | $0.177 | 153.77 | no | $0.028 | Anthropic |  |
| claude_mixed | $0.199 | 172.99 | no | $0.040 | Anthropic |  |

### What each step uses in the profiles that fit, and what it costs (big plan)

**proven**

| Step | Model | Calls | Cost (thinking included) |
|---|---|---|---|
| triage_specialist | `gemini-3.1-flash-lite` | 1 | $0.0005 |
| project_manager | `gemini-3.1-flash-lite` | 1 | $0.0055 |
| safety_quality_gatekeeper | `gemini-3.1-flash-lite` | 1 | $0.0009 |
| cognitive_worker | `gemini-3.1-flash-lite` | 25 | $0.022 |
| mcp_operator | `gemini-3.1-flash-lite` | 5 | $0.0039 |
| data_engineer | `gemini-3.1-flash-lite` | 5 | $0.0047 |
| draft_writer | `gemini-3.1-flash-lite` | 1 | $0.0042 |
| editor_in_chief | `gemini-3.1-flash-lite` | 1 | $0.0017 |
| answer_checker | `gemini-3.1-flash-lite` | 0 | $0 |
| user_clarification | `gemini-3.1-flash-lite` | 0 | $0 |
| **Total** | | 40 | **$0.044** = 37.90 EUR per 1,000 messages |

Every step on gemini-3.1-flash-lite, which has an end-to-end run (2026-09-21) and answered a test call on 2026-10-28. It replaces gemini-2.5-flash, the first model tested end to end, which Google no longer gives to new keys. Active since 2026-10-28: on the free tier it answered 10 calls in a row, while gemini-3.6-flash (profile google_free) returned 429 after about 7 calls in 30 s.

**budget**

| Step | Model | Calls | Cost (thinking included) |
|---|---|---|---|
| triage_specialist | `gemini-3.1-flash-lite` | 1 | $0.0005 |
| project_manager | `gemini-3.5-flash-lite` | 1 | $0.0095 |
| safety_quality_gatekeeper | `gemini-3.1-flash-lite` | 1 | $0.0009 |
| cognitive_worker | `gemini-3.1-flash-lite` | 25 | $0.022 |
| mcp_operator | `gemini-3.5-flash-lite` | 5 | $0.0063 |
| data_engineer | `gemini-3.1-flash-lite` | 5 | $0.0047 |
| draft_writer | `gemini-3.1-flash-lite` | 1 | $0.0042 |
| editor_in_chief | `gemini-3.1-flash-lite` | 1 | $0.0017 |
| answer_checker | `gemini-3.1-flash-lite` | 0 | $0 |
| user_clarification | `gemini-3.1-flash-lite` | 0 | $0 |
| **Total** | | 40 | **$0.050** = 43.45 EUR per 1,000 messages |

The cheapest that should work: gemini-3.1-flash-lite everywhere except the planner and the tool step (gemini-3.5-flash-lite). Untested. It replaces the gemini-2.5-flash-lite and gemini-2.5-flash of the first version, which Google no longer gives to new keys.

**budget50**

| Step | Model | Calls | Cost (thinking included) |
|---|---|---|---|
| triage_specialist | `gemini-3.1-flash-lite` | 1 | $0.0005 |
| project_manager | `gemini-3.5-flash-lite` | 1 | $0.0095 |
| safety_quality_gatekeeper | `gemini-3.1-flash-lite` | 1 | $0.0009 |
| cognitive_worker | `gemini-3.1-flash-lite` | 25 | $0.022 |
| mcp_operator | `gemini-3.1-flash-lite` | 5 | $0.0039 |
| data_engineer | `gemini-3.1-flash-lite` | 5 | $0.0047 |
| draft_writer | `gemini-3.1-flash-lite` | 1 | $0.0042 |
| editor_in_chief | `gemini-3.1-flash-lite` | 1 | $0.0017 |
| answer_checker | `gemini-3.1-flash-lite` | 0 | $0 |
| user_clarification | `gemini-3.1-flash-lite` | 0 | $0 |
| **Total** | | 40 | **$0.048** = 41.38 EUR per 1,000 messages |

Fits 50 EUR for 1,000 messages even if every message has a plan of 30 actions. Google models only. gemini-3.1-flash-lite for almost everything (it does not think, so it costs little), gemini-3.5-flash-lite for the planner (the one step that needs reasoning: a Lite model, rated ok). Untested as a combination. It replaces gemini-2.5-flash for the planner and gemini-2.5-flash-lite for three steps, which Google no longer gives to new keys.

**budget50_groq**

| Step | Model | Calls | Cost (thinking included) |
|---|---|---|---|
| triage_specialist | `gemini-3.1-flash-lite` | 1 | $0.0005 |
| project_manager | `openai/gpt-oss-120b` | 1 | $0.0054 |
| safety_quality_gatekeeper | `openai/gpt-oss-120b` | 1 | $0.0006 |
| cognitive_worker | `openai/gpt-oss-120b` | 25 | $0.018 |
| mcp_operator | `gemini-3.1-flash-lite` | 5 | $0.0039 |
| data_engineer | `gemini-3.1-flash-lite` | 5 | $0.0047 |
| draft_writer | `openai/gpt-oss-120b` | 1 | $0.0030 |
| editor_in_chief | `openai/gpt-oss-120b` | 1 | $0.0015 |
| answer_checker | `gemini-3.1-flash-lite` | 0 | $0 |
| user_clarification | `gemini-3.1-flash-lite` | 0 | $0 |
| **Total** | | 40 | **$0.038** = 32.76 EUR per 1,000 messages |

Cheaper than budget50: the planner, the gate, the worker, the draft and the editor use openai/gpt-oss-120b on Groq (strong reasoning at 0.15 in and 0.60 out per 1M tokens, tested end to end). Triage, tools, cleaning, the checker and the question use gemini-3.1-flash-lite. Needs GROQ_API_KEY and GROQ_URL. Untested as a combination.

To use one: `windows\Scripts\python.exe tests\manual\show_models.py --profile=budget50` (then `--step=<step>` and `--set=<step>=<model id>` to change a step).

## 3. All the models, cheapest first

`Works today`: **yes, tested** = run end to end through this agent with this project's key, 0 problems; **should (no key to test)** = the API accepts what the agent sends, but there is no key in `.env`; **needs adapter change** = the agent would have to change first (see the note under the table).

| # | Name | Provider | Model id | In $/1M | Out $/1M | Blended $/1M | Works today | Reasoning |
|---|---|---|---|---|---|---|---|---|
| 1 | GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | 0.13 | yes, tested | reasoning model: its reasoning is inside the counted output tokens (about 2.5x the visible answer) |
| 2 | GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40* | 0.14 | needs adapter change | reasoning model: reasoning tokens are billed as output |
| 3 | GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | 0.26 | yes, tested | reasoning model: its reasoning is inside the counted output tokens (about 2.5x the visible answer) |
| 4 | GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | 0.45 | needs adapter change | reasoning model (assumed): reasoning tokens are billed as output |
| 5 | Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | 0.56 | yes, tested | not stated in the pages read |
| 6 | GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00* | 0.69 | needs adapter change | reasoning model: reasoning tokens are billed as output |
| 7 | Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | 0.85 | yes, tested | minimal by default |
| 8 | Gemini 3 Flash (preview) | Google | `gemini-3-flash-preview` | 0.500 | 3.00 | 1.12 | yes, tested | a test call used 20 thinking tokens (2026-10-28); not stated in the pages read |
| 9 | Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | 1.50 | yes, tested | medium by default. Can go down to 'minimal'. |
| 10 | Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | 1.50 | yes, tested | medium by default |
| 11 | GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | 1.69 | needs adapter change | reasoning model (assumed): reasoning tokens are billed as output |
| 12 | Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | 2.00 | yes, tested | no extended thinking unless asked |
| 13 | Gemini 4 Argon | Google | `gemini-4-argon` | 2.000 | 10.00* | 4.00 | should (no key to test) | not stated in the pages read |
| 14 | Claude Sonnet 5 (Anthropic) | Anthropic | `claude-sonnet-5` | 2.000 | 10.00 | 4.00 | should (no key to test) | no extended thinking unless asked |
| 15 | Claude Sonnet 5.5 (Anthropic) | Anthropic | `claude-sonnet-5-5` | 2.000 | 10.00 | 4.00 | yes, tested | adaptive thinking (Anthropic: Sonnet 5.5 decides how much to think, steered by effort) |
| 16 | Gemini 3.1 Pro (preview) | Google | `gemini-3.1-pro-preview` | 2.000 | 12.00* | 4.50 | yes, tested | always on |
| 17 | GPT-5.6 Terra (OpenAI) | OpenAI | `gpt-5.6-terra` | 2.000 | 12.00 | 4.50 | needs adapter change | reasoning model (assumed): reasoning tokens are billed as output |

\* GPT-5 nano (OpenAI): OpenAI lists it as deprecated; it is shut down on 2026-12-11 (replacement: gpt-5.6-luna for nano, gpt-5.6-terra for mini).
\* GPT-5 mini (OpenAI): OpenAI lists it as deprecated; it is shut down on 2026-12-11 (replacement: gpt-5.6-luna for nano, gpt-5.6-terra for mini).
\* Gemini 3.6 Flash: until 2026-12-31. From 2027-01-01: 1.50 in, 7.50 out.
\* Gemini 3.8 Flash: until 2026-12-31. From 2027-01-01: 1.50 in, 7.50 out.
\* Gemini 4 Argon: until 2026-11-30. From 2026-12-01: 4.00 in, 20.00 out.
\* Gemini 3.1 Pro (preview): prompts up to 200k tokens. Above: 4.00 in, 18.00 out.

Notes on what each model needs:

- `gpt-5-nano`: GPT-5 models reject max_tokens (they need max_completion_tokens). Needs an OpenAI key.
- `gpt-5.6-luna`: GPT-5.x models reject max_tokens (they need max_completion_tokens). Needs an OpenAI key.
- `gpt-5-mini`: GPT-5 models reject max_tokens (they need max_completion_tokens). Needs an OpenAI key.
- `gpt-5.4-mini`: GPT-5.x models reject max_tokens (they need max_completion_tokens). Needs an OpenAI key.
- `gemini-4-argon`: not called: no free tier (listed by the API for this key on 2026-10-28)
- `claude-sonnet-5`: Same route as claude-haiku-4-5, which works end to end (ADR-013); answered a one-word call on 2026-10-28 (check_google_ids.py --provider=anthropic); not run in a flow. Needs an Anthropic key. Claude 5 thinks by default and the endpoint hides it.
- `gpt-5.6-terra`: GPT-5.x models reject max_tokens (they need max_completion_tokens). Needs an OpenAI key.

## 4. One table per step

Each table lists the models rated better than **avoid** for the step, cheapest first. `Cost of the step` is what all the calls of that step cost in one message with the big plan, thinking included. `Per 1,000 messages` is the same in EUR.

### triage_specialist

Classifies the request into a small JSON. Runs first, so latency matters. Little reasoning, but it must not ask for details it does not need.

Big plan: 1 call(s), 1,260 tokens sent and 150 answered (measured per call with gemini-2.5-flash: 1,650 tokens; measured with gemini-2.5-flash: 1,500 to 1,700).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0.0002 | 0.18 | yes, tested | **good** | `"triage_specialist": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40* | $0.0002 | 0.19 | needs adapter change | **good** | `"triage_specialist": "gpt-5-nano"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0.0004 | 0.36 | yes, tested | **good** | `"triage_specialist": "openai/gpt-oss-120b"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0.0006 | 0.53 | needs adapter change | **good** | `"triage_specialist": "gpt-5.6-luna"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0.0005 | 0.47 | yes, tested | **best** | `"triage_specialist": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00* | $0.0011 | 0.93 | needs adapter change | **ok** | `"triage_specialist": "gpt-5-mini"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0.0009 | 0.76 | yes, tested | **best** | `"triage_specialist": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | Google | `gemini-3-flash-preview` | 0.500 | 3.00 | $0.0018 | 1.58 | yes, tested | **ok** | `"triage_specialist": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0.0033 | 2.91 | yes, tested | **ok** | `"triage_specialist": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0.0033 | 2.91 | yes, tested | **ok** | `"triage_specialist": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0.0023 | 2.00 | needs adapter change | **ok** | `"triage_specialist": "gpt-5.4-mini"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0.0020 | 1.75 | yes, tested | **ok** | `"triage_specialist": "claude-haiku-4-5"` |

### project_manager

The hardest step. Builds the plan: a recursive action tree with dependencies, types and tool choice, in a strict schema. Needs real reasoning. One call per message.

Big plan: 1 call(s), 1,600 tokens sent and 3,420 answered (measured per call with gemini-2.5-flash: 2,150 tokens; measured with gemini-2.5-flash: about 2,150).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0.0027 | 2.34 | yes, tested | **ok** | `"project_manager": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40* | $0.0035 | 3.05 | needs adapter change | **ok** | `"project_manager": "gpt-5-nano"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0.0054 | 4.67 | yes, tested | **best** | `"project_manager": "openai/gpt-oss-120b"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0.0085 | 7.42 | needs adapter change | **ok** | `"project_manager": "gpt-5.6-luna"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0.0055 | 4.81 | yes, tested | **ok** | `"project_manager": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00* | $0.018 | 15.23 | needs adapter change | **good** | `"project_manager": "gpt-5-mini"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0.0095 | 8.29 | yes, tested | **ok** | `"project_manager": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | Google | `gemini-3-flash-preview` | 0.500 | 3.00 | $0.014 | 12.20 | yes, tested | **ok** | `"project_manager": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0.021 | 18.64 | yes, tested | **good** | `"project_manager": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0.021 | 18.64 | yes, tested | **best** | `"project_manager": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0.032 | 27.83 | needs adapter change | **good** | `"project_manager": "gpt-5.4-mini"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0.019 | 16.28 | yes, tested | **good** | `"project_manager": "claude-haiku-4-5"` |
| Gemini 4 Argon | Google | `gemini-4-argon` | 2.000 | 10.00* | $0.067 | 58.27 | should (no key to test) | **best** | `"project_manager": "gemini-4-argon"` |
| Claude Sonnet 5 (Anthropic) | Anthropic | `claude-sonnet-5` | 2.000 | 10.00 | $0.037 | 32.55 | should (no key to test) | **best** | `"project_manager": "claude-sonnet-5"` |
| Claude Sonnet 5.5 (Anthropic) | Anthropic | `claude-sonnet-5-5` | 2.000 | 10.00 | $0.037 | 32.55 | yes, tested | **best** | `"project_manager": "claude-sonnet-5-5"` |
| Gemini 3.1 Pro (preview) | Google | `gemini-3.1-pro-preview` | 2.000 | 12.00* | $0.080 | 69.36 | yes, tested | **best** | `"project_manager": "gemini-3.1-pro-preview"` |
| GPT-5.6 Terra (OpenAI) | OpenAI | `gpt-5.6-terra` | 2.000 | 12.00 | $0.085 | 74.22 | needs adapter change | **best** | `"project_manager": "gpt-5.6-terra"` |

### safety_quality_gatekeeper

Judges the plan for risk and decides if the user must confirm. Small JSON, judgement more than reasoning. One call.

Big plan: 1 call(s), 3,170 tokens sent and 55 answered (measured per call with gemini-2.5-flash: 1,500 tokens; measured with gemini-2.5-flash: 1,350 to 1,700).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0.0003 | 0.24 | yes, tested | **good** | `"safety_quality_gatekeeper": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40* | $0.0002 | 0.19 | needs adapter change | **ok** | `"safety_quality_gatekeeper": "gpt-5-nano"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0.0006 | 0.49 | yes, tested | **good** | `"safety_quality_gatekeeper": "openai/gpt-oss-120b"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0.0008 | 0.67 | needs adapter change | **good** | `"safety_quality_gatekeeper": "gpt-5.6-luna"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0.0009 | 0.76 | yes, tested | **good** | `"safety_quality_gatekeeper": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00* | $0.0011 | 0.93 | needs adapter change | **good** | `"safety_quality_gatekeeper": "gpt-5-mini"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0.0011 | 1.00 | yes, tested | **good** | `"safety_quality_gatekeeper": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | Google | `gemini-3-flash-preview` | 0.500 | 3.00 | $0.0021 | 1.82 | yes, tested | **good** | `"safety_quality_gatekeeper": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0.0034 | 3.00 | yes, tested | **good** | `"safety_quality_gatekeeper": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0.0034 | 3.00 | yes, tested | **good** | `"safety_quality_gatekeeper": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0.0029 | 2.50 | needs adapter change | **good** | `"safety_quality_gatekeeper": "gpt-5.4-mini"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0.0034 | 3.00 | yes, tested | **good** | `"safety_quality_gatekeeper": "claude-haiku-4-5"` |
| Gemini 4 Argon | Google | `gemini-4-argon` | 2.000 | 10.00* | $0.010 | 9.01 | should (no key to test) | **good** | `"safety_quality_gatekeeper": "gemini-4-argon"` |
| Claude Sonnet 5 (Anthropic) | Anthropic | `claude-sonnet-5` | 2.000 | 10.00 | $0.0069 | 6.00 | should (no key to test) | **best** | `"safety_quality_gatekeeper": "claude-sonnet-5"` |
| Claude Sonnet 5.5 (Anthropic) | Anthropic | `claude-sonnet-5-5` | 2.000 | 10.00 | $0.0069 | 6.00 | yes, tested | **best** | `"safety_quality_gatekeeper": "claude-sonnet-5-5"` |
| Gemini 3.1 Pro (preview) | Google | `gemini-3.1-pro-preview` | 2.000 | 12.00* | $0.011 | 9.71 | yes, tested | **good** | `"safety_quality_gatekeeper": "gemini-3.1-pro-preview"` |
| GPT-5.6 Terra (OpenAI) | OpenAI | `gpt-5.6-terra` | 2.000 | 12.00 | $0.0077 | 6.67 | needs adapter change | **good** | `"safety_quality_gatekeeper": "gpt-5.6-terra"` |

### cognitive_worker

One call per action of the plan: answers, analyses, writes a piece. The quality of the content comes from here. The number of calls grows with the plan.

Big plan: 25 call(s), 40,250 tokens sent and 8,000 answered (measured per call with gemini-2.5-flash: 1,270 tokens; measured with gemini-2.5-flash: about 1,270 per action).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0.0090 | 7.85 | yes, tested | **good** | `"cognitive_worker": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40* | $0.010 | 8.71 | needs adapter change | **ok** | `"cognitive_worker": "gpt-5-nano"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0.018 | 15.70 | yes, tested | **good** | `"cognitive_worker": "openai/gpt-oss-120b"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0.027 | 23.72 | needs adapter change | **good** | `"cognitive_worker": "gpt-5.6-luna"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0.022 | 19.20 | yes, tested | **good** | `"cognitive_worker": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00* | $0.050 | 43.57 | needs adapter change | **good** | `"cognitive_worker": "gpt-5-mini"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0.037 | 31.85 | yes, tested | **good** | `"cognitive_worker": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | Google | `gemini-3-flash-preview` | 0.500 | 3.00 | $0.071 | 62.03 | yes, tested | **good** | `"cognitive_worker": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0.128 | 111.46 | yes, tested | **best** | `"cognitive_worker": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0.128 | 111.46 | yes, tested | **best** | `"cognitive_worker": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0.102 | 88.94 | needs adapter change | **good** | `"cognitive_worker": "gpt-5.4-mini"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0.080 | 69.84 | yes, tested | **good** | `"cognitive_worker": "claude-haiku-4-5"` |
| Gemini 4 Argon | Google | `gemini-4-argon` | 2.000 | 10.00* | $0.432 | 375.98 | should (no key to test) | **good** | `"cognitive_worker": "gemini-4-argon"` |
| Claude Sonnet 5 (Anthropic) | Anthropic | `claude-sonnet-5` | 2.000 | 10.00 | $0.161 | 139.69 | should (no key to test) | **best** | `"cognitive_worker": "claude-sonnet-5"` |
| Claude Sonnet 5.5 (Anthropic) | Anthropic | `claude-sonnet-5-5` | 2.000 | 10.00 | $0.161 | 139.69 | yes, tested | **best** | `"cognitive_worker": "claude-sonnet-5-5"` |
| Gemini 3.1 Pro (preview) | Google | `gemini-3.1-pro-preview` | 2.000 | 12.00* | $0.502 | 437.16 | yes, tested | **good** | `"cognitive_worker": "gemini-3.1-pro-preview"` |
| GPT-5.6 Terra (OpenAI) | OpenAI | `gpt-5.6-terra` | 2.000 | 12.00 | $0.273 | 237.16 | needs adapter change | **good** | `"cognitive_worker": "gpt-5.6-terra"` |

### mcp_operator

One or more calls per tool action. Needs reliable function calling plus a valid JSON answer.

Big plan: 5 call(s), 9,500 tokens sent and 1,000 answered (measured per call with gemini-2.5-flash: 1,600 tokens; estimate, not measured: the tool list makes the prompt longer).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0.0015 | 1.27 | yes, tested | **ok** | `"mcp_operator": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40* | $0.0015 | 1.28 | needs adapter change | **weak** | `"mcp_operator": "gpt-5-nano"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0.0029 | 2.55 | yes, tested | **good** | `"mcp_operator": "openai/gpt-oss-120b"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0.0043 | 3.74 | needs adapter change | **good** | `"mcp_operator": "gpt-5.6-luna"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0.0039 | 3.37 | yes, tested | **good** | `"mcp_operator": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00* | $0.0074 | 6.42 | needs adapter change | **good** | `"mcp_operator": "gpt-5-mini"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0.0063 | 5.44 | yes, tested | **good** | `"mcp_operator": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | Google | `gemini-3-flash-preview` | 0.500 | 3.00 | $0.013 | 11.47 | yes, tested | **good** | `"mcp_operator": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0.024 | 21.28 | yes, tested | **good** | `"mcp_operator": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0.024 | 21.28 | yes, tested | **best** | `"mcp_operator": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0.016 | 14.03 | needs adapter change | **good** | `"mcp_operator": "gpt-5.4-mini"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0.015 | 12.62 | yes, tested | **good** | `"mcp_operator": "claude-haiku-4-5"` |
| Gemini 4 Argon | Google | `gemini-4-argon` | 2.000 | 10.00* | $0.083 | 72.50 | should (no key to test) | **good** | `"mcp_operator": "gemini-4-argon"` |
| Claude Sonnet 5 (Anthropic) | Anthropic | `claude-sonnet-5` | 2.000 | 10.00 | $0.029 | 25.24 | should (no key to test) | **best** | `"mcp_operator": "claude-sonnet-5"` |
| Claude Sonnet 5.5 (Anthropic) | Anthropic | `claude-sonnet-5-5` | 2.000 | 10.00 | $0.029 | 25.24 | yes, tested | **best** | `"mcp_operator": "claude-sonnet-5-5"` |
| Gemini 3.1 Pro (preview) | Google | `gemini-3.1-pro-preview` | 2.000 | 12.00* | $0.096 | 83.69 | yes, tested | **good** | `"mcp_operator": "gemini-3.1-pro-preview"` |
| GPT-5.6 Terra (OpenAI) | OpenAI | `gpt-5.6-terra` | 2.000 | 12.00 | $0.043 | 37.42 | needs adapter change | **best** | `"mcp_operator": "gpt-5.6-terra"` |

### data_engineer

Cleans the output of a tool. Mechanical: precision, no creativity.

Big plan: 5 call(s), 7,000 tokens sent and 2,000 answered (measured per call with gemini-2.5-flash: 1,100 tokens; estimate, not measured).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0.0020 | 1.76 | yes, tested | **good** | `"data_engineer": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40* | $0.0024 | 2.05 | needs adapter change | **good** | `"data_engineer": "gpt-5-nano"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0.0040 | 3.52 | yes, tested | **ok** | `"data_engineer": "openai/gpt-oss-120b"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0.0062 | 5.40 | needs adapter change | **good** | `"data_engineer": "gpt-5.6-luna"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0.0047 | 4.13 | yes, tested | **best** | `"data_engineer": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00* | $0.012 | 10.23 | needs adapter change | **ok** | `"data_engineer": "gpt-5-mini"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0.0074 | 6.43 | yes, tested | **good** | `"data_engineer": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | Google | `gemini-3-flash-preview` | 0.500 | 3.00 | $0.011 | 9.78 | yes, tested | **ok** | `"data_engineer": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0.017 | 14.87 | yes, tested | **ok** | `"data_engineer": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0.017 | 14.87 | yes, tested | **ok** | `"data_engineer": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0.023 | 20.23 | needs adapter change | **ok** | `"data_engineer": "gpt-5.4-mini"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0.017 | 14.80 | yes, tested | **ok** | `"data_engineer": "claude-haiku-4-5"` |

### draft_writer

Writes the first answer for the user from all the outputs. Writing quality and following the constraints.

Big plan: 1 call(s), 12,190 tokens sent and 800 answered (measured per call with gemini-2.5-flash: 1,150 tokens; measured with gemini-2.5-flash: about 1,150).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0.0015 | 1.32 | yes, tested | **ok** | `"draft_writer": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40* | $0.0014 | 1.23 | needs adapter change | **ok** | `"draft_writer": "gpt-5-nano"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0.0030 | 2.64 | yes, tested | **good** | `"draft_writer": "openai/gpt-oss-120b"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0.0044 | 3.79 | needs adapter change | **good** | `"draft_writer": "gpt-5.6-luna"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0.0042 | 3.70 | yes, tested | **good** | `"draft_writer": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00* | $0.0070 | 6.13 | needs adapter change | **good** | `"draft_writer": "gpt-5-mini"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0.0057 | 5.00 | yes, tested | **good** | `"draft_writer": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | Google | `gemini-3-flash-preview` | 0.500 | 3.00 | $0.0090 | 7.84 | yes, tested | **good** | `"draft_writer": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0.013 | 11.69 | yes, tested | **best** | `"draft_writer": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0.013 | 11.69 | yes, tested | **best** | `"draft_writer": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0.016 | 14.22 | needs adapter change | **good** | `"draft_writer": "gpt-5.4-mini"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0.016 | 14.09 | yes, tested | **good** | `"draft_writer": "claude-haiku-4-5"` |
| Gemini 4 Argon | Google | `gemini-4-argon` | 2.000 | 10.00* | $0.038 | 32.67 | should (no key to test) | **good** | `"draft_writer": "gemini-4-argon"` |
| Claude Sonnet 5 (Anthropic) | Anthropic | `claude-sonnet-5` | 2.000 | 10.00 | $0.032 | 28.18 | should (no key to test) | **best** | `"draft_writer": "claude-sonnet-5"` |
| Claude Sonnet 5.5 (Anthropic) | Anthropic | `claude-sonnet-5-5` | 2.000 | 10.00 | $0.032 | 28.18 | yes, tested | **best** | `"draft_writer": "claude-sonnet-5-5"` |
| Gemini 3.1 Pro (preview) | Google | `gemini-3.1-pro-preview` | 2.000 | 12.00* | $0.040 | 34.96 | yes, tested | **good** | `"draft_writer": "gemini-3.1-pro-preview"` |
| GPT-5.6 Terra (OpenAI) | OpenAI | `gpt-5.6-terra` | 2.000 | 12.00 | $0.044 | 37.93 | needs adapter change | **best** | `"draft_writer": "gpt-5.6-terra"` |

### editor_in_chief

Polishes the draft without adding facts and sets the final status. Faithfulness more than creativity.

Big plan: 1 call(s), 1,890 tokens sent and 800 answered (measured per call with gemini-2.5-flash: 1,400 tokens; measured with gemini-2.5-flash: 1,300 to 1,500).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0.0007 | 0.65 | yes, tested | **ok** | `"editor_in_chief": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40* | $0.0009 | 0.78 | needs adapter change | **ok** | `"editor_in_chief": "gpt-5-nano"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0.0015 | 1.29 | yes, tested | **good** | `"editor_in_chief": "openai/gpt-oss-120b"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0.0023 | 2.00 | needs adapter change | **good** | `"editor_in_chief": "gpt-5.6-luna"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0.0017 | 1.46 | yes, tested | **good** | `"editor_in_chief": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00* | $0.0045 | 3.89 | needs adapter change | **good** | `"editor_in_chief": "gpt-5-mini"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0.0026 | 2.26 | yes, tested | **good** | `"editor_in_chief": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | Google | `gemini-3-flash-preview` | 0.500 | 3.00 | $0.0035 | 3.06 | yes, tested | **good** | `"editor_in_chief": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0.0048 | 4.22 | yes, tested | **good** | `"editor_in_chief": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0.0048 | 4.22 | yes, tested | **best** | `"editor_in_chief": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0.0086 | 7.50 | needs adapter change | **good** | `"editor_in_chief": "gpt-5.4-mini"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0.0059 | 5.13 | yes, tested | **good** | `"editor_in_chief": "claude-haiku-4-5"` |
| Gemini 4 Argon | Google | `gemini-4-argon` | 2.000 | 10.00* | $0.014 | 11.75 | should (no key to test) | **ok** | `"editor_in_chief": "gemini-4-argon"` |
| Claude Sonnet 5 (Anthropic) | Anthropic | `claude-sonnet-5` | 2.000 | 10.00 | $0.012 | 10.25 | should (no key to test) | **good** | `"editor_in_chief": "claude-sonnet-5"` |
| Claude Sonnet 5.5 (Anthropic) | Anthropic | `claude-sonnet-5-5` | 2.000 | 10.00 | $0.012 | 10.25 | yes, tested | **good** | `"editor_in_chief": "claude-sonnet-5-5"` |
| Gemini 3.1 Pro (preview) | Google | `gemini-3.1-pro-preview` | 2.000 | 12.00* | $0.015 | 13.45 | yes, tested | **ok** | `"editor_in_chief": "gemini-3.1-pro-preview"` |
| GPT-5.6 Terra (OpenAI) | OpenAI | `gpt-5.6-terra` | 2.000 | 12.00 | $0.023 | 20.00 | needs adapter change | **good** | `"editor_in_chief": "gpt-5.6-terra"` |

### answer_checker

Reads the user's reply to a question: an answer, a yes or a no, not an answer, or stop. Short, any language, latency matters.

Big plan: 0 call(s), 0 tokens sent and 0 answered (measured per call with gemini-2.5-flash: 1,200 tokens; measured with gemini-2.5-flash: about 1,200).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0 | 0 | yes, tested | **best** | `"answer_checker": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40* | $0 | 0 | needs adapter change | **good** | `"answer_checker": "gpt-5-nano"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0 | 0 | yes, tested | **good** | `"answer_checker": "openai/gpt-oss-120b"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0 | 0 | needs adapter change | **good** | `"answer_checker": "gpt-5.6-luna"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0 | 0 | yes, tested | **best** | `"answer_checker": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00* | $0 | 0 | needs adapter change | **ok** | `"answer_checker": "gpt-5-mini"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0 | 0 | yes, tested | **best** | `"answer_checker": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | Google | `gemini-3-flash-preview` | 0.500 | 3.00 | $0 | 0 | yes, tested | **ok** | `"answer_checker": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0 | 0 | yes, tested | **ok** | `"answer_checker": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0 | 0 | yes, tested | **ok** | `"answer_checker": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0 | 0 | needs adapter change | **ok** | `"answer_checker": "gpt-5.4-mini"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0 | 0 | yes, tested | **ok** | `"answer_checker": "claude-haiku-4-5"` |

### user_clarification

Writes a short friendly question for the user. Trivial.

Big plan: 0 call(s), 0 tokens sent and 0 answered (measured per call with gemini-2.5-flash: 130 tokens; measured with gemini-2.5-flash: about 130).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0 | 0 | yes, tested | **best** | `"user_clarification": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40* | $0 | 0 | needs adapter change | **good** | `"user_clarification": "gpt-5-nano"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0 | 0 | yes, tested | **good** | `"user_clarification": "openai/gpt-oss-120b"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0 | 0 | needs adapter change | **best** | `"user_clarification": "gpt-5.6-luna"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0 | 0 | yes, tested | **best** | `"user_clarification": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00* | $0 | 0 | needs adapter change | **ok** | `"user_clarification": "gpt-5-mini"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0 | 0 | yes, tested | **best** | `"user_clarification": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | Google | `gemini-3-flash-preview` | 0.500 | 3.00 | $0 | 0 | yes, tested | **ok** | `"user_clarification": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0 | 0 | yes, tested | **ok** | `"user_clarification": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0 | 0 | yes, tested | **ok** | `"user_clarification": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0 | 0 | needs adapter change | **ok** | `"user_clarification": "gpt-5.4-mini"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0 | 0 | yes, tested | **good** | `"user_clarification": "claude-haiku-4-5"` |

## 5. How to choose

1. One profile for every step: `windows\Scripts\python.exe tests\manual\show_models.py --profile=budget50`.
2. One step: `windows\Scripts\python.exe tests\manual\show_models.py --set=project_manager=openai/gpt-oss-120b` (or write the line of the table in `steps` of `config/step_models.json`). Only models the agent's provider table knows can be chosen (`domain/value_objects/llm_request/model_catalog.py`).
3. See what is in use with its price: `windows\Scripts\python.exe tests\manual\show_models.py`.
4. Before you trust a model on a step: `tests/manual/debug_flow.py --real`, then `--only=<step> --state=<file> --repeat=5`. The problems it finds and `compare.md` show if the model is steady.
5. To change the budget, the rate or the size of the plans: `config/budget.json`, then `show_models.py --budget`.
