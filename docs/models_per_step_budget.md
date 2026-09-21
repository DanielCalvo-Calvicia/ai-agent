# Models for each step, within a budget

_Generated from `config/gemini_models.json`, `config/other_models.json`, `config/measured_runs.json` and `config/budget.json` by `tests/manual/show_models.py --budget`. Edit those files, not this one._

## The budget

- **50 EUR a month at most, for 1,000 messages** = 0.050 EUR = **$0.0575 per message** (ECB euro reference exchange rate (1 EUR = 1.1490 USD on 2026-09-21; it moved between 1.146 and 1.170 in the last 30 days)).
- The worst case is used: **every message has a big plan of 30 actions** (5 actions with 5 subactions each, 5 of them with a tool). A message with a small plan of 2 actions costs far less, so the real month will be under the budget.
- Prices and status: Google's pages ai.google.dev/gemini-api/docs/pricing, /models and /thinking, read on 2026-09-21. Prices are USD per 1M tokens, text, standard paid tier, and the output price includes thinking tokens. Check the page before you rely on a number.
- Prices: OpenAI developers.openai.com/api/docs/pricing, Anthropic platform.claude.com/docs/en/about-claude/pricing, mistral.ai/pricing/api, DeepSeek api-docs.deepseek.com/quick_start/pricing and Groq console.groq.com/docs/models, read on 2026-09-21 through a page summariser. USD per 1M tokens, standard tier. Check them before you rely on a number. The Gemini models are in gemini_models.json.
- The ratings are estimates from the size and description of each model, NOT measurements. Only the models marked tested were run here. Ratings: **best** = the right model for this step; **good** = works well, a fair price for the job; **ok** = works, but slower, weaker or more expensive than needed; **weak** = likely to fail or to give poor results here; **avoid** = wasteful (too expensive or too slow for what the step does).

## 1. What was measured, and what it changes

One real message was sent through the whole agent with each model on every step ("Compare Python, Go and Rust. For each language give two strengths and two weaknesses, then recommend one for a beginner and explain why."). Tokens as the provider counted them; **thinking = total - sent - answered**.

| Model | Calls | Sent | Answered | Thinking | Cost of that message | Per 1,000 such messages |
|---|---|---|---|---|---|---|
| `openai/gpt-oss-20b` | 6 | 10,161 | 4,300 | 0 | $0.0021 | $2.05 = 1.79 EUR |
| `gemini-2.5-flash-lite` | 10 | 11,672 | 2,310 | 2 | $0.0021 | $2.09 = 1.82 EUR |
| `openai/gpt-oss-120b` | 6 | 10,393 | 3,885 | 0 | $0.0039 | $3.89 = 3.39 EUR |
| `gemini-3.1-flash-lite` | 7 | 8,938 | 1,487 | 0 | $0.0045 | $4.46 = 3.89 EUR |
| `gemini-2.5-flash` | 10 | 12,305 | 3,194 | 2,484 | $0.018 | $17.89 = 15.57 EUR |
| `gemini-3.8-flash` | 7 | 9,757 | 2,357 | 3,611 | $0.030 | $29.70 = 25.85 EUR |

- **Thinking is billed, and the API hides it.** `gemini-2.5-flash` thought 2,484 tokens for 3,194 answered (44% more output) and `gemini-3.8-flash` 3,611 for 2,357 (150% more). Google's `completion_tokens` does not include them; only `total_tokens` does. The two lite models thought nothing. This is why the Flash models cost 4 to 14 times more than the lite ones on the same message.
- `openai/gpt-oss` (Groq) is a reasoning model too, but its reasoning is inside the counted output tokens (about 2.5 times the visible answer, measured), and its price is low: it cost about the same as the lite models.
- A switch exists to turn thinking off: with `reasoning_effort="none"` `gemini-2.5-flash` thought 0 tokens instead of 411 on a test question (tested with a direct call). The agent does not send it yet, so a thinking model is still billed for thinking.

## 2. Profiles and their cost

Cost of one message, thinking included. The limit is **$0.0575 (0.050 EUR)**. Big plan = 30 actions; small plan = 2 actions.

| Profile | Big plan, USD | Big plan, EUR per 1,000 messages | Fits the budget? | Small plan, USD | Providers | Active |
|---|---|---|---|---|---|---|
| strongest (per step, from the earlier table) | $0.350 | 304.37 | no | $0.055 | Anthropic, Google, OpenAI |  |
| proven | $0.109 | 95.01 | no | $0.018 | Google |  |
| budget | $0.035 | 30.86 | **yes** | $0.0067 | Google |  |
| balanced | $0.104 | 90.28 | no | $0.021 | Google |  |
| quality | $0.260 | 225.91 | no | $0.066 | Google |  |
| budget50 | $0.047 | 41.12 | **yes** | $0.011 | Google |  |
| budget50_groq | $0.034 | 29.93 | **yes** | $0.0060 | Google, Groq | yes |

### What each step uses in the profiles that fit, and what it costs (big plan)

**budget**

| Step | Model | Calls | Cost (thinking included) |
|---|---|---|---|
| triage_specialist | `gemini-2.5-flash-lite` | 1 | $0.0002 |
| project_manager | `gemini-2.5-flash` | 1 | $0.012 |
| safety_quality_gatekeeper | `gemini-2.5-flash-lite` | 1 | $0.0003 |
| cognitive_worker | `gemini-2.5-flash-lite` | 25 | $0.0072 |
| mcp_operator | `gemini-2.5-flash` | 5 | $0.012 |
| data_engineer | `gemini-2.5-flash-lite` | 5 | $0.0015 |
| draft_writer | `gemini-2.5-flash-lite` | 1 | $0.0015 |
| editor_in_chief | `gemini-2.5-flash-lite` | 1 | $0.0005 |
| answer_checker | `gemini-2.5-flash-lite` | 0 | $0 |
| user_clarification | `gemini-2.5-flash-lite` | 0 | $0 |
| **Total** | | 40 | **$0.035** = 30.86 EUR per 1,000 messages |

The cheapest that should work: lite models everywhere except the planner and the tool step. Untested.

**budget50**

| Step | Model | Calls | Cost (thinking included) |
|---|---|---|---|
| triage_specialist | `gemini-3.1-flash-lite` | 1 | $0.0005 |
| project_manager | `gemini-2.5-flash` | 1 | $0.012 |
| safety_quality_gatekeeper | `gemini-3.1-flash-lite` | 1 | $0.0009 |
| cognitive_worker | `gemini-3.1-flash-lite` | 25 | $0.022 |
| mcp_operator | `gemini-3.1-flash-lite` | 5 | $0.0039 |
| data_engineer | `gemini-2.5-flash-lite` | 5 | $0.0015 |
| draft_writer | `gemini-3.1-flash-lite` | 1 | $0.0042 |
| editor_in_chief | `gemini-3.1-flash-lite` | 1 | $0.0017 |
| answer_checker | `gemini-2.5-flash-lite` | 0 | $0 |
| user_clarification | `gemini-2.5-flash-lite` | 0 | $0 |
| **Total** | | 40 | **$0.047** = 41.12 EUR per 1,000 messages |

Fits 50 EUR for 1,000 messages even if every message has a plan of 30 actions. Google models only. Lite models for almost everything (they do not think, so they cost little), gemini-2.5-flash for the planner (the one step that needs reasoning, and the model tested for it). Untested as a combination.

**budget50_groq**

| Step | Model | Calls | Cost (thinking included) |
|---|---|---|---|
| triage_specialist | `gemini-3.1-flash-lite` | 1 | $0.0005 |
| project_manager | `openai/gpt-oss-120b` | 1 | $0.0054 |
| safety_quality_gatekeeper | `openai/gpt-oss-120b` | 1 | $0.0006 |
| cognitive_worker | `openai/gpt-oss-120b` | 25 | $0.018 |
| mcp_operator | `gemini-3.1-flash-lite` | 5 | $0.0039 |
| data_engineer | `gemini-2.5-flash-lite` | 5 | $0.0015 |
| draft_writer | `openai/gpt-oss-120b` | 1 | $0.0030 |
| editor_in_chief | `openai/gpt-oss-120b` | 1 | $0.0015 |
| answer_checker | `gemini-2.5-flash-lite` | 0 | $0 |
| user_clarification | `gemini-2.5-flash-lite` | 0 | $0 |
| **Total** | | 40 | **$0.034** = 29.93 EUR per 1,000 messages |

Cheaper than budget50: the planner, the gate, the worker, the draft and the editor use openai/gpt-oss-120b on Groq (strong reasoning at 0.15 in and 0.60 out per 1M tokens, tested end to end). Triage, tools, cleaning, the checker and the question use Google lite models. Needs GROQ_API_KEY and GROQ_URL. Untested as a combination.

To use one: `windows\Scripts\python.exe tests\manual\show_models.py --profile=budget50` (then `--step=<step>` and `--set=<step>=<model id>` to change a step).

## 3. All the models, cheapest first

`Works today`: **yes, tested** = run end to end through this agent with this project's key, 0 problems; **should (no key to test)** = the API accepts what the agent sends, but there is no key in `.env`; **needs adapter change** = the agent would have to change first (see the note under the table).

| # | Name | Provider | Model id | In $/1M | Out $/1M | Blended $/1M | Works today | Reasoning |
|---|---|---|---|---|---|---|---|---|
| 1 | GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | 0.13 | yes, tested | reasoning model: its reasoning is inside the counted output tokens (about 2.5x the visible answer) |
| 2 | GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40 | 0.14 | needs adapter change | reasoning model: reasoning tokens are billed as output |
| 3 | Gemini 2.5 Flash-Lite | Google | `gemini-2.5-flash-lite` | 0.100 | 0.40 | 0.18 | yes, tested | off by default (the fastest) |
| 4 | GPT-4.1 nano (OpenAI) | OpenAI | `gpt-4.1-nano` | 0.100 | 0.40 | 0.18 | should (no key to test) | no reasoning |
| 5 | Ministral 3 14B (Mistral) | Mistral | `ministral-3-14b-25-12` | 0.200 | 0.20 | 0.20 | should (no key to test) | not stated |
| 6 | GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | 0.26 | yes, tested | reasoning model: its reasoning is inside the counted output tokens (about 2.5x the visible answer) |
| 7 | Mistral Small 4 (Mistral) | Mistral | `mistral-small-4-0-26-03` | 0.150 | 0.60 | 0.26 | should (no key to test) | not stated |
| 8 | GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | 0.45 | needs adapter change | reasoning model (assumed): reasoning tokens are billed as output |
| 9 | DeepSeek Flash (DeepSeek) | DeepSeek | `deepseek-flash` | 0.300 | 1.20* | 0.52 | needs adapter change | thinking mode exists; how it is billed was not checked |
| 10 | Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | 0.56 | yes, tested | not stated in the pages read |
| 11 | GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00 | 0.69 | needs adapter change | reasoning model: reasoning tokens are billed as output |
| 12 | GPT-4.1 mini (OpenAI) | OpenAI | `gpt-4.1-mini` | 0.400 | 1.60 | 0.70 | should (no key to test) | no reasoning |
| 13 | Mistral Large 3 (Mistral) | Mistral | `mistral-large-3-25-12` | 0.500 | 1.50 | 0.75 | should (no key to test) | not stated |
| 14 | Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | 0.85 | yes, tested | minimal by default |
| 15 | Gemini 2.5 Flash | Google | `gemini-2.5-flash` | 0.300 | 2.50 | 0.85 | yes, tested | always on (the lowest level is 'low') |
| 16 | Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | 1.50 | yes, tested | medium by default. Can go down to 'minimal'. |
| 17 | Gemini 3.7 Flash | Google | `gemini-3.7-flash` | 0.750 | 3.75* | 1.50 | yes, tested | medium by default |
| 18 | Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | 1.50 | yes, tested | medium by default |
| 19 | GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | 1.69 | needs adapter change | reasoning model (assumed): reasoning tokens are billed as output |
| 20 | DeepSeek V4 Pro (DeepSeek) | DeepSeek | `deepseek-v4-pro` | 1.320 | 3.96* | 1.98 | needs adapter change | thinking mode exists; how it is billed was not checked |
| 21 | Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | 2.00 | needs adapter change | no extended thinking unless asked |
| 22 | Gemini 3.5 Flash | Google | `gemini-3.5-flash` | 1.500 | 9.00 | 3.38 | yes, tested | not stated in the pages read |
| 23 | Gemini 2.5 Pro | Google | `gemini-2.5-pro` | 1.250 | 10.00* | 3.44 | no (API refused it) | always on |
| 24 | Claude Sonnet 5 (Anthropic) | Anthropic | `claude-sonnet-5` | 2.000 | 10.00 | 4.00 | needs adapter change | no extended thinking unless asked |
| 25 | Gemini 3.1 Pro (preview) | Google | `gemini-3.1-pro-preview` | 2.000 | 12.00* | 4.50 | yes, tested | always on |
| 26 | GPT-5.6 Terra (OpenAI) | OpenAI | `gpt-5.6-terra` | 2.000 | 12.00 | 4.50 | needs adapter change | reasoning model (assumed): reasoning tokens are billed as output |

\* DeepSeek Flash (DeepSeek): peak hours 01:00-04:00 and 06:00-10:00 UTC on weekdays. Off-peak: 0.15 in, 0.60 out.
\* Gemini 3.6 Flash: until 2026-12-31. From 2027-01-01: 1.50 in, 7.50 out.
\* Gemini 3.7 Flash: until 2026-12-31. From 2027-01-01: 1.50 in, 7.50 out.
\* Gemini 3.8 Flash: until 2026-12-31. From 2027-01-01: 1.50 in, 7.50 out.
\* DeepSeek V4 Pro (DeepSeek): peak hours 01:00-04:00 and 06:00-10:00 UTC on weekdays. Off-peak: 0.66 in, 1.98 out.
\* Gemini 2.5 Pro: prompts up to 200k tokens. Above: 2.50 in, 15.00 out.
\* Gemini 3.1 Pro (preview): prompts up to 200k tokens. Above: 4.00 in, 18.00 out.

Notes on what each model needs:

- `gpt-5-nano`: GPT-5 models reject max_tokens (they need max_completion_tokens). Needs an OpenAI key.
- `gpt-4.1-nano`: Accepts max_tokens and json_schema. Needs an OpenAI key. Not tested here.
- `ministral-3-14b-25-12`: OpenAI-compatible API. Needs a Mistral key. Not tested here.
- `mistral-small-4-0-26-03`: OpenAI-compatible API with json_schema. Needs a Mistral key (none in .env). Not tested here.
- `gpt-5.6-luna`: GPT-5.x models reject max_tokens (they need max_completion_tokens). Needs an OpenAI key.
- `deepseek-flash`: Only JSON mode (json_object), not json_schema, and it is not in the provider table of the agent. Data is processed outside the EU.
- `gpt-5-mini`: GPT-5 models reject max_tokens (they need max_completion_tokens). Needs an OpenAI key.
- `gpt-4.1-mini`: Accepts max_tokens and json_schema. Needs an OpenAI key. Not tested here.
- `mistral-large-3-25-12`: OpenAI-compatible API with json_schema. Needs a Mistral key. Not tested here.
- `gpt-5.4-mini`: GPT-5.x models reject max_tokens (they need max_completion_tokens). Needs an OpenAI key.
- `deepseek-v4-pro`: Only JSON mode (json_object), not json_schema, and it is not in the provider table of the agent. Data is processed outside the EU.
- `claude-haiku-4-5`: Needs Anthropic's own API for structured output (the OpenAI-compatible layer does not enforce json_schema). Needs an Anthropic key.
- `gemini-2.5-pro`: FAILED: 404, 'no longer available to new users'
- `claude-sonnet-5`: Needs Anthropic's own API for structured output. Needs an Anthropic key.
- `gpt-5.6-terra`: GPT-5.x models reject max_tokens (they need max_completion_tokens). Needs an OpenAI key.

## 4. One table per step

Each table lists the models rated better than **avoid** for the step, cheapest first. `Cost of the step` is what all the calls of that step cost in one message with the big plan, thinking included. `Per 1,000 messages` is the same in EUR.

### triage_specialist

Classifies the request into a small JSON. Runs first, so latency matters. Little reasoning, but it must not ask for details it does not need.

Big plan: 1 call(s), 1,260 tokens sent and 150 answered (measured per call with gemini-2.5-flash: 1,650 tokens; measured with gemini-2.5-flash: 1,500 to 1,700).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0.0002 | 0.18 | yes, tested | **good** | `"triage_specialist": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40 | $0.0002 | 0.19 | needs adapter change | **good** | `"triage_specialist": "gpt-5-nano"` |
| Gemini 2.5 Flash-Lite | Google | `gemini-2.5-flash-lite` | 0.100 | 0.40 | $0.0002 | 0.16 | yes, tested | **good** | `"triage_specialist": "gemini-2.5-flash-lite"` |
| GPT-4.1 nano (OpenAI) | OpenAI | `gpt-4.1-nano` | 0.100 | 0.40 | $0.0002 | 0.16 | should (no key to test) | **good** | `"triage_specialist": "gpt-4.1-nano"` |
| Ministral 3 14B (Mistral) | Mistral | `ministral-3-14b-25-12` | 0.200 | 0.20 | $0.0003 | 0.25 | should (no key to test) | **good** | `"triage_specialist": "ministral-3-14b-25-12"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0.0004 | 0.36 | yes, tested | **good** | `"triage_specialist": "openai/gpt-oss-120b"` |
| Mistral Small 4 (Mistral) | Mistral | `mistral-small-4-0-26-03` | 0.150 | 0.60 | $0.0003 | 0.24 | should (no key to test) | **good** | `"triage_specialist": "mistral-small-4-0-26-03"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0.0006 | 0.53 | needs adapter change | **good** | `"triage_specialist": "gpt-5.6-luna"` |
| DeepSeek Flash (DeepSeek) | DeepSeek | `deepseek-flash` | 0.300 | 1.20* | $0.0006 | 0.49 | needs adapter change | **good** | `"triage_specialist": "deepseek-flash"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0.0005 | 0.47 | yes, tested | **best** | `"triage_specialist": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00 | $0.0011 | 0.93 | needs adapter change | **ok** | `"triage_specialist": "gpt-5-mini"` |
| GPT-4.1 mini (OpenAI) | OpenAI | `gpt-4.1-mini` | 0.400 | 1.60 | $0.0007 | 0.65 | should (no key to test) | **good** | `"triage_specialist": "gpt-4.1-mini"` |
| Mistral Large 3 (Mistral) | Mistral | `mistral-large-3-25-12` | 0.500 | 1.50 | $0.0009 | 0.74 | should (no key to test) | **ok** | `"triage_specialist": "mistral-large-3-25-12"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0.0009 | 0.76 | yes, tested | **best** | `"triage_specialist": "gemini-3.5-flash-lite"` |
| Gemini 2.5 Flash | Google | `gemini-2.5-flash` | 0.300 | 2.50 | $0.0016 | 1.40 | yes, tested | **ok** | `"triage_specialist": "gemini-2.5-flash"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0.0033 | 2.91 | yes, tested | **ok** | `"triage_specialist": "gemini-3.6-flash"` |
| Gemini 3.7 Flash | Google | `gemini-3.7-flash` | 0.750 | 3.75* | $0.0033 | 2.91 | yes, tested | **ok** | `"triage_specialist": "gemini-3.7-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0.0033 | 2.91 | yes, tested | **ok** | `"triage_specialist": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0.0023 | 2.00 | needs adapter change | **ok** | `"triage_specialist": "gpt-5.4-mini"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0.0020 | 1.75 | needs adapter change | **ok** | `"triage_specialist": "claude-haiku-4-5"` |

### project_manager

The hardest step. Builds the plan: a recursive action tree with dependencies, types and tool choice, in a strict schema. Needs real reasoning. One call per message.

Big plan: 1 call(s), 1,600 tokens sent and 3,420 answered (measured per call with gemini-2.5-flash: 2,150 tokens; measured with gemini-2.5-flash: about 2,150).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0.0027 | 2.34 | yes, tested | **ok** | `"project_manager": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40 | $0.0035 | 3.05 | needs adapter change | **ok** | `"project_manager": "gpt-5-nano"` |
| Gemini 2.5 Flash-Lite | Google | `gemini-2.5-flash-lite` | 0.100 | 0.40 | $0.0015 | 1.33 | yes, tested | **weak** | `"project_manager": "gemini-2.5-flash-lite"` |
| GPT-4.1 nano (OpenAI) | OpenAI | `gpt-4.1-nano` | 0.100 | 0.40 | $0.0015 | 1.33 | should (no key to test) | **weak** | `"project_manager": "gpt-4.1-nano"` |
| Ministral 3 14B (Mistral) | Mistral | `ministral-3-14b-25-12` | 0.200 | 0.20 | $0.0010 | 0.87 | should (no key to test) | **weak** | `"project_manager": "ministral-3-14b-25-12"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0.0054 | 4.67 | yes, tested | **best** | `"project_manager": "openai/gpt-oss-120b"` |
| Mistral Small 4 (Mistral) | Mistral | `mistral-small-4-0-26-03` | 0.150 | 0.60 | $0.0023 | 1.99 | should (no key to test) | **ok** | `"project_manager": "mistral-small-4-0-26-03"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0.0085 | 7.42 | needs adapter change | **ok** | `"project_manager": "gpt-5.6-luna"` |
| DeepSeek Flash (DeepSeek) | DeepSeek | `deepseek-flash` | 0.300 | 1.20* | $0.0046 | 3.99 | needs adapter change | **good** | `"project_manager": "deepseek-flash"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0.0055 | 4.81 | yes, tested | **ok** | `"project_manager": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00 | $0.018 | 15.23 | needs adapter change | **good** | `"project_manager": "gpt-5-mini"` |
| GPT-4.1 mini (OpenAI) | OpenAI | `gpt-4.1-mini` | 0.400 | 1.60 | $0.0061 | 5.32 | should (no key to test) | **ok** | `"project_manager": "gpt-4.1-mini"` |
| Mistral Large 3 (Mistral) | Mistral | `mistral-large-3-25-12` | 0.500 | 1.50 | $0.0059 | 5.16 | should (no key to test) | **good** | `"project_manager": "mistral-large-3-25-12"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0.0095 | 8.29 | yes, tested | **ok** | `"project_manager": "gemini-3.5-flash-lite"` |
| Gemini 2.5 Flash | Google | `gemini-2.5-flash` | 0.300 | 2.50 | $0.012 | 10.86 | yes, tested | **good** | `"project_manager": "gemini-2.5-flash"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0.021 | 18.64 | yes, tested | **good** | `"project_manager": "gemini-3.6-flash"` |
| Gemini 3.7 Flash | Google | `gemini-3.7-flash` | 0.750 | 3.75* | $0.021 | 18.64 | yes, tested | **good** | `"project_manager": "gemini-3.7-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0.021 | 18.64 | yes, tested | **best** | `"project_manager": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0.032 | 27.83 | needs adapter change | **good** | `"project_manager": "gpt-5.4-mini"` |
| DeepSeek V4 Pro (DeepSeek) | DeepSeek | `deepseek-v4-pro` | 1.320 | 3.96* | $0.016 | 13.63 | needs adapter change | **best** | `"project_manager": "deepseek-v4-pro"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0.019 | 16.28 | needs adapter change | **good** | `"project_manager": "claude-haiku-4-5"` |
| Gemini 3.5 Flash | Google | `gemini-3.5-flash` | 1.500 | 9.00 | $0.051 | 44.31 | yes, tested | **ok** | `"project_manager": "gemini-3.5-flash"` |
| Claude Sonnet 5 (Anthropic) | Anthropic | `claude-sonnet-5` | 2.000 | 10.00 | $0.037 | 32.55 | needs adapter change | **best** | `"project_manager": "claude-sonnet-5"` |
| Gemini 3.1 Pro (preview) | Google | `gemini-3.1-pro-preview` | 2.000 | 12.00* | $0.080 | 69.36 | yes, tested | **best** | `"project_manager": "gemini-3.1-pro-preview"` |
| GPT-5.6 Terra (OpenAI) | OpenAI | `gpt-5.6-terra` | 2.000 | 12.00 | $0.085 | 74.22 | needs adapter change | **best** | `"project_manager": "gpt-5.6-terra"` |

### safety_quality_gatekeeper

Judges the plan for risk and decides if the user must confirm. Small JSON, judgement more than reasoning. One call.

Big plan: 1 call(s), 3,170 tokens sent and 55 answered (measured per call with gemini-2.5-flash: 1,500 tokens; measured with gemini-2.5-flash: 1,350 to 1,700).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0.0003 | 0.24 | yes, tested | **good** | `"safety_quality_gatekeeper": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40 | $0.0002 | 0.19 | needs adapter change | **ok** | `"safety_quality_gatekeeper": "gpt-5-nano"` |
| Gemini 2.5 Flash-Lite | Google | `gemini-2.5-flash-lite` | 0.100 | 0.40 | $0.0003 | 0.30 | yes, tested | **ok** | `"safety_quality_gatekeeper": "gemini-2.5-flash-lite"` |
| GPT-4.1 nano (OpenAI) | OpenAI | `gpt-4.1-nano` | 0.100 | 0.40 | $0.0003 | 0.30 | should (no key to test) | **ok** | `"safety_quality_gatekeeper": "gpt-4.1-nano"` |
| Ministral 3 14B (Mistral) | Mistral | `ministral-3-14b-25-12` | 0.200 | 0.20 | $0.0006 | 0.56 | should (no key to test) | **ok** | `"safety_quality_gatekeeper": "ministral-3-14b-25-12"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0.0006 | 0.49 | yes, tested | **good** | `"safety_quality_gatekeeper": "openai/gpt-oss-120b"` |
| Mistral Small 4 (Mistral) | Mistral | `mistral-small-4-0-26-03` | 0.150 | 0.60 | $0.0005 | 0.44 | should (no key to test) | **good** | `"safety_quality_gatekeeper": "mistral-small-4-0-26-03"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0.0008 | 0.67 | needs adapter change | **good** | `"safety_quality_gatekeeper": "gpt-5.6-luna"` |
| DeepSeek Flash (DeepSeek) | DeepSeek | `deepseek-flash` | 0.300 | 1.20* | $0.0010 | 0.89 | needs adapter change | **good** | `"safety_quality_gatekeeper": "deepseek-flash"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0.0009 | 0.76 | yes, tested | **good** | `"safety_quality_gatekeeper": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00 | $0.0011 | 0.93 | needs adapter change | **good** | `"safety_quality_gatekeeper": "gpt-5-mini"` |
| GPT-4.1 mini (OpenAI) | OpenAI | `gpt-4.1-mini` | 0.400 | 1.60 | $0.0014 | 1.18 | should (no key to test) | **good** | `"safety_quality_gatekeeper": "gpt-4.1-mini"` |
| Mistral Large 3 (Mistral) | Mistral | `mistral-large-3-25-12` | 0.500 | 1.50 | $0.0017 | 1.45 | should (no key to test) | **good** | `"safety_quality_gatekeeper": "mistral-large-3-25-12"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0.0011 | 1.00 | yes, tested | **good** | `"safety_quality_gatekeeper": "gemini-3.5-flash-lite"` |
| Gemini 2.5 Flash | Google | `gemini-2.5-flash` | 0.300 | 2.50 | $0.0015 | 1.30 | yes, tested | **good** | `"safety_quality_gatekeeper": "gemini-2.5-flash"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0.0034 | 3.00 | yes, tested | **good** | `"safety_quality_gatekeeper": "gemini-3.6-flash"` |
| Gemini 3.7 Flash | Google | `gemini-3.7-flash` | 0.750 | 3.75* | $0.0034 | 3.00 | yes, tested | **good** | `"safety_quality_gatekeeper": "gemini-3.7-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0.0034 | 3.00 | yes, tested | **good** | `"safety_quality_gatekeeper": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0.0029 | 2.50 | needs adapter change | **good** | `"safety_quality_gatekeeper": "gpt-5.4-mini"` |
| DeepSeek V4 Pro (DeepSeek) | DeepSeek | `deepseek-v4-pro` | 1.320 | 3.96* | $0.0044 | 3.83 | needs adapter change | **good** | `"safety_quality_gatekeeper": "deepseek-v4-pro"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0.0034 | 3.00 | needs adapter change | **good** | `"safety_quality_gatekeeper": "claude-haiku-4-5"` |
| Gemini 3.5 Flash | Google | `gemini-3.5-flash` | 1.500 | 9.00 | $0.0073 | 6.38 | yes, tested | **ok** | `"safety_quality_gatekeeper": "gemini-3.5-flash"` |
| Claude Sonnet 5 (Anthropic) | Anthropic | `claude-sonnet-5` | 2.000 | 10.00 | $0.0069 | 6.00 | needs adapter change | **best** | `"safety_quality_gatekeeper": "claude-sonnet-5"` |
| Gemini 3.1 Pro (preview) | Google | `gemini-3.1-pro-preview` | 2.000 | 12.00* | $0.011 | 9.71 | yes, tested | **good** | `"safety_quality_gatekeeper": "gemini-3.1-pro-preview"` |
| GPT-5.6 Terra (OpenAI) | OpenAI | `gpt-5.6-terra` | 2.000 | 12.00 | $0.0077 | 6.67 | needs adapter change | **good** | `"safety_quality_gatekeeper": "gpt-5.6-terra"` |

### cognitive_worker

One call per action of the plan: answers, analyses, writes a piece. The quality of the content comes from here. The number of calls grows with the plan.

Big plan: 25 call(s), 40,250 tokens sent and 8,000 answered (measured per call with gemini-2.5-flash: 1,270 tokens; measured with gemini-2.5-flash: about 1,270 per action).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0.0090 | 7.85 | yes, tested | **good** | `"cognitive_worker": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40 | $0.010 | 8.71 | needs adapter change | **ok** | `"cognitive_worker": "gpt-5-nano"` |
| Gemini 2.5 Flash-Lite | Google | `gemini-2.5-flash-lite` | 0.100 | 0.40 | $0.0072 | 6.29 | yes, tested | **ok** | `"cognitive_worker": "gemini-2.5-flash-lite"` |
| GPT-4.1 nano (OpenAI) | OpenAI | `gpt-4.1-nano` | 0.100 | 0.40 | $0.0072 | 6.29 | should (no key to test) | **ok** | `"cognitive_worker": "gpt-4.1-nano"` |
| Ministral 3 14B (Mistral) | Mistral | `ministral-3-14b-25-12` | 0.200 | 0.20 | $0.0097 | 8.40 | should (no key to test) | **ok** | `"cognitive_worker": "ministral-3-14b-25-12"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0.018 | 15.70 | yes, tested | **good** | `"cognitive_worker": "openai/gpt-oss-120b"` |
| Mistral Small 4 (Mistral) | Mistral | `mistral-small-4-0-26-03` | 0.150 | 0.60 | $0.011 | 9.43 | should (no key to test) | **good** | `"cognitive_worker": "mistral-small-4-0-26-03"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0.027 | 23.72 | needs adapter change | **good** | `"cognitive_worker": "gpt-5.6-luna"` |
| DeepSeek Flash (DeepSeek) | DeepSeek | `deepseek-flash` | 0.300 | 1.20* | $0.022 | 18.86 | needs adapter change | **good** | `"cognitive_worker": "deepseek-flash"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0.022 | 19.20 | yes, tested | **good** | `"cognitive_worker": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00 | $0.050 | 43.57 | needs adapter change | **good** | `"cognitive_worker": "gpt-5-mini"` |
| GPT-4.1 mini (OpenAI) | OpenAI | `gpt-4.1-mini` | 0.400 | 1.60 | $0.029 | 25.15 | should (no key to test) | **good** | `"cognitive_worker": "gpt-4.1-mini"` |
| Mistral Large 3 (Mistral) | Mistral | `mistral-large-3-25-12` | 0.500 | 1.50 | $0.032 | 27.96 | should (no key to test) | **best** | `"cognitive_worker": "mistral-large-3-25-12"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0.037 | 31.85 | yes, tested | **good** | `"cognitive_worker": "gemini-3.5-flash-lite"` |
| Gemini 2.5 Flash | Google | `gemini-2.5-flash` | 0.300 | 2.50 | $0.064 | 55.48 | yes, tested | **good** | `"cognitive_worker": "gemini-2.5-flash"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0.128 | 111.46 | yes, tested | **best** | `"cognitive_worker": "gemini-3.6-flash"` |
| Gemini 3.7 Flash | Google | `gemini-3.7-flash` | 0.750 | 3.75* | $0.128 | 111.46 | yes, tested | **best** | `"cognitive_worker": "gemini-3.7-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0.128 | 111.46 | yes, tested | **best** | `"cognitive_worker": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0.102 | 88.94 | needs adapter change | **good** | `"cognitive_worker": "gpt-5.4-mini"` |
| DeepSeek V4 Pro (DeepSeek) | DeepSeek | `deepseek-v4-pro` | 1.320 | 3.96* | $0.085 | 73.81 | needs adapter change | **best** | `"cognitive_worker": "deepseek-v4-pro"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0.080 | 69.84 | needs adapter change | **good** | `"cognitive_worker": "claude-haiku-4-5"` |
| Gemini 3.5 Flash | Google | `gemini-3.5-flash` | 1.500 | 9.00 | $0.295 | 256.98 | yes, tested | **ok** | `"cognitive_worker": "gemini-3.5-flash"` |
| Claude Sonnet 5 (Anthropic) | Anthropic | `claude-sonnet-5` | 2.000 | 10.00 | $0.161 | 139.69 | needs adapter change | **best** | `"cognitive_worker": "claude-sonnet-5"` |
| Gemini 3.1 Pro (preview) | Google | `gemini-3.1-pro-preview` | 2.000 | 12.00* | $0.502 | 437.16 | yes, tested | **good** | `"cognitive_worker": "gemini-3.1-pro-preview"` |
| GPT-5.6 Terra (OpenAI) | OpenAI | `gpt-5.6-terra` | 2.000 | 12.00 | $0.273 | 237.16 | needs adapter change | **good** | `"cognitive_worker": "gpt-5.6-terra"` |

### mcp_operator

One or more calls per tool action. Needs reliable function calling plus a valid JSON answer.

Big plan: 5 call(s), 9,500 tokens sent and 1,000 answered (measured per call with gemini-2.5-flash: 1,600 tokens; estimate, not measured: the tool list makes the prompt longer).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0.0015 | 1.27 | yes, tested | **ok** | `"mcp_operator": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40 | $0.0015 | 1.28 | needs adapter change | **weak** | `"mcp_operator": "gpt-5-nano"` |
| Gemini 2.5 Flash-Lite | Google | `gemini-2.5-flash-lite` | 0.100 | 0.40 | $0.0014 | 1.17 | yes, tested | **weak** | `"mcp_operator": "gemini-2.5-flash-lite"` |
| GPT-4.1 nano (OpenAI) | OpenAI | `gpt-4.1-nano` | 0.100 | 0.40 | $0.0014 | 1.17 | should (no key to test) | **weak** | `"mcp_operator": "gpt-4.1-nano"` |
| Ministral 3 14B (Mistral) | Mistral | `ministral-3-14b-25-12` | 0.200 | 0.20 | $0.0021 | 1.83 | should (no key to test) | **weak** | `"mcp_operator": "ministral-3-14b-25-12"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0.0029 | 2.55 | yes, tested | **good** | `"mcp_operator": "openai/gpt-oss-120b"` |
| Mistral Small 4 (Mistral) | Mistral | `mistral-small-4-0-26-03` | 0.150 | 0.60 | $0.0020 | 1.76 | should (no key to test) | **good** | `"mcp_operator": "mistral-small-4-0-26-03"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0.0043 | 3.74 | needs adapter change | **good** | `"mcp_operator": "gpt-5.6-luna"` |
| DeepSeek Flash (DeepSeek) | DeepSeek | `deepseek-flash` | 0.300 | 1.20* | $0.0040 | 3.52 | needs adapter change | **good** | `"mcp_operator": "deepseek-flash"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0.0039 | 3.37 | yes, tested | **good** | `"mcp_operator": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00 | $0.0074 | 6.42 | needs adapter change | **good** | `"mcp_operator": "gpt-5-mini"` |
| GPT-4.1 mini (OpenAI) | OpenAI | `gpt-4.1-mini` | 0.400 | 1.60 | $0.0054 | 4.70 | should (no key to test) | **good** | `"mcp_operator": "gpt-4.1-mini"` |
| Mistral Large 3 (Mistral) | Mistral | `mistral-large-3-25-12` | 0.500 | 1.50 | $0.0063 | 5.44 | should (no key to test) | **good** | `"mcp_operator": "mistral-large-3-25-12"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0.0063 | 5.44 | yes, tested | **good** | `"mcp_operator": "gemini-3.5-flash-lite"` |
| Gemini 2.5 Flash | Google | `gemini-2.5-flash` | 0.300 | 2.50 | $0.012 | 10.17 | yes, tested | **good** | `"mcp_operator": "gemini-2.5-flash"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0.024 | 21.28 | yes, tested | **good** | `"mcp_operator": "gemini-3.6-flash"` |
| Gemini 3.7 Flash | Google | `gemini-3.7-flash` | 0.750 | 3.75* | $0.024 | 21.28 | yes, tested | **best** | `"mcp_operator": "gemini-3.7-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0.024 | 21.28 | yes, tested | **best** | `"mcp_operator": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0.016 | 14.03 | needs adapter change | **good** | `"mcp_operator": "gpt-5.4-mini"` |
| DeepSeek V4 Pro (DeepSeek) | DeepSeek | `deepseek-v4-pro` | 1.320 | 3.96* | $0.017 | 14.36 | needs adapter change | **good** | `"mcp_operator": "deepseek-v4-pro"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0.015 | 12.62 | needs adapter change | **good** | `"mcp_operator": "claude-haiku-4-5"` |
| Gemini 3.5 Flash | Google | `gemini-3.5-flash` | 1.500 | 9.00 | $0.056 | 48.59 | yes, tested | **ok** | `"mcp_operator": "gemini-3.5-flash"` |
| Claude Sonnet 5 (Anthropic) | Anthropic | `claude-sonnet-5` | 2.000 | 10.00 | $0.029 | 25.24 | needs adapter change | **best** | `"mcp_operator": "claude-sonnet-5"` |
| Gemini 3.1 Pro (preview) | Google | `gemini-3.1-pro-preview` | 2.000 | 12.00* | $0.096 | 83.69 | yes, tested | **good** | `"mcp_operator": "gemini-3.1-pro-preview"` |
| GPT-5.6 Terra (OpenAI) | OpenAI | `gpt-5.6-terra` | 2.000 | 12.00 | $0.043 | 37.42 | needs adapter change | **best** | `"mcp_operator": "gpt-5.6-terra"` |

### data_engineer

Cleans the output of a tool. Mechanical: precision, no creativity.

Big plan: 5 call(s), 7,000 tokens sent and 2,000 answered (measured per call with gemini-2.5-flash: 1,100 tokens; estimate, not measured).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0.0020 | 1.76 | yes, tested | **good** | `"data_engineer": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40 | $0.0024 | 2.05 | needs adapter change | **good** | `"data_engineer": "gpt-5-nano"` |
| Gemini 2.5 Flash-Lite | Google | `gemini-2.5-flash-lite` | 0.100 | 0.40 | $0.0015 | 1.31 | yes, tested | **best** | `"data_engineer": "gemini-2.5-flash-lite"` |
| GPT-4.1 nano (OpenAI) | OpenAI | `gpt-4.1-nano` | 0.100 | 0.40 | $0.0015 | 1.31 | should (no key to test) | **best** | `"data_engineer": "gpt-4.1-nano"` |
| Ministral 3 14B (Mistral) | Mistral | `ministral-3-14b-25-12` | 0.200 | 0.20 | $0.0018 | 1.57 | should (no key to test) | **good** | `"data_engineer": "ministral-3-14b-25-12"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0.0040 | 3.52 | yes, tested | **ok** | `"data_engineer": "openai/gpt-oss-120b"` |
| Mistral Small 4 (Mistral) | Mistral | `mistral-small-4-0-26-03` | 0.150 | 0.60 | $0.0022 | 1.96 | should (no key to test) | **good** | `"data_engineer": "mistral-small-4-0-26-03"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0.0062 | 5.40 | needs adapter change | **good** | `"data_engineer": "gpt-5.6-luna"` |
| DeepSeek Flash (DeepSeek) | DeepSeek | `deepseek-flash` | 0.300 | 1.20* | $0.0045 | 3.92 | needs adapter change | **good** | `"data_engineer": "deepseek-flash"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0.0047 | 4.13 | yes, tested | **best** | `"data_engineer": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00 | $0.012 | 10.23 | needs adapter change | **ok** | `"data_engineer": "gpt-5-mini"` |
| GPT-4.1 mini (OpenAI) | OpenAI | `gpt-4.1-mini` | 0.400 | 1.60 | $0.0060 | 5.22 | should (no key to test) | **good** | `"data_engineer": "gpt-4.1-mini"` |
| Mistral Large 3 (Mistral) | Mistral | `mistral-large-3-25-12` | 0.500 | 1.50 | $0.0065 | 5.66 | should (no key to test) | **ok** | `"data_engineer": "mistral-large-3-25-12"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0.0074 | 6.43 | yes, tested | **good** | `"data_engineer": "gemini-3.5-flash-lite"` |
| Gemini 2.5 Flash | Google | `gemini-2.5-flash` | 0.300 | 2.50 | $0.0091 | 7.94 | yes, tested | **ok** | `"data_engineer": "gemini-2.5-flash"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0.017 | 14.87 | yes, tested | **ok** | `"data_engineer": "gemini-3.6-flash"` |
| Gemini 3.7 Flash | Google | `gemini-3.7-flash` | 0.750 | 3.75* | $0.017 | 14.87 | yes, tested | **ok** | `"data_engineer": "gemini-3.7-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0.017 | 14.87 | yes, tested | **ok** | `"data_engineer": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0.023 | 20.23 | needs adapter change | **ok** | `"data_engineer": "gpt-5.4-mini"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0.017 | 14.80 | needs adapter change | **ok** | `"data_engineer": "claude-haiku-4-5"` |

### draft_writer

Writes the first answer for the user from all the outputs. Writing quality and following the constraints.

Big plan: 1 call(s), 12,190 tokens sent and 800 answered (measured per call with gemini-2.5-flash: 1,150 tokens; measured with gemini-2.5-flash: about 1,150).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0.0015 | 1.32 | yes, tested | **ok** | `"draft_writer": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40 | $0.0014 | 1.23 | needs adapter change | **ok** | `"draft_writer": "gpt-5-nano"` |
| Gemini 2.5 Flash-Lite | Google | `gemini-2.5-flash-lite` | 0.100 | 0.40 | $0.0015 | 1.34 | yes, tested | **ok** | `"draft_writer": "gemini-2.5-flash-lite"` |
| GPT-4.1 nano (OpenAI) | OpenAI | `gpt-4.1-nano` | 0.100 | 0.40 | $0.0015 | 1.34 | should (no key to test) | **ok** | `"draft_writer": "gpt-4.1-nano"` |
| Ministral 3 14B (Mistral) | Mistral | `ministral-3-14b-25-12` | 0.200 | 0.20 | $0.0026 | 2.26 | should (no key to test) | **ok** | `"draft_writer": "ministral-3-14b-25-12"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0.0030 | 2.64 | yes, tested | **good** | `"draft_writer": "openai/gpt-oss-120b"` |
| Mistral Small 4 (Mistral) | Mistral | `mistral-small-4-0-26-03` | 0.150 | 0.60 | $0.0023 | 2.01 | should (no key to test) | **good** | `"draft_writer": "mistral-small-4-0-26-03"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0.0044 | 3.79 | needs adapter change | **good** | `"draft_writer": "gpt-5.6-luna"` |
| DeepSeek Flash (DeepSeek) | DeepSeek | `deepseek-flash` | 0.300 | 1.20* | $0.0046 | 4.02 | needs adapter change | **good** | `"draft_writer": "deepseek-flash"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0.0042 | 3.70 | yes, tested | **good** | `"draft_writer": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00 | $0.0070 | 6.13 | needs adapter change | **good** | `"draft_writer": "gpt-5-mini"` |
| GPT-4.1 mini (OpenAI) | OpenAI | `gpt-4.1-mini` | 0.400 | 1.60 | $0.0062 | 5.36 | should (no key to test) | **good** | `"draft_writer": "gpt-4.1-mini"` |
| Mistral Large 3 (Mistral) | Mistral | `mistral-large-3-25-12` | 0.500 | 1.50 | $0.0073 | 6.35 | should (no key to test) | **best** | `"draft_writer": "mistral-large-3-25-12"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0.0057 | 5.00 | yes, tested | **good** | `"draft_writer": "gemini-3.5-flash-lite"` |
| Gemini 2.5 Flash | Google | `gemini-2.5-flash` | 0.300 | 2.50 | $0.0063 | 5.45 | yes, tested | **good** | `"draft_writer": "gemini-2.5-flash"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0.013 | 11.69 | yes, tested | **best** | `"draft_writer": "gemini-3.6-flash"` |
| Gemini 3.7 Flash | Google | `gemini-3.7-flash` | 0.750 | 3.75* | $0.013 | 11.69 | yes, tested | **best** | `"draft_writer": "gemini-3.7-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0.013 | 11.69 | yes, tested | **best** | `"draft_writer": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0.016 | 14.22 | needs adapter change | **good** | `"draft_writer": "gpt-5.4-mini"` |
| DeepSeek V4 Pro (DeepSeek) | DeepSeek | `deepseek-v4-pro` | 1.320 | 3.96* | $0.019 | 16.76 | needs adapter change | **best** | `"draft_writer": "deepseek-v4-pro"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0.016 | 14.09 | needs adapter change | **good** | `"draft_writer": "claude-haiku-4-5"` |
| Gemini 3.5 Flash | Google | `gemini-3.5-flash` | 1.500 | 9.00 | $0.029 | 24.87 | yes, tested | **ok** | `"draft_writer": "gemini-3.5-flash"` |
| Claude Sonnet 5 (Anthropic) | Anthropic | `claude-sonnet-5` | 2.000 | 10.00 | $0.032 | 28.18 | needs adapter change | **best** | `"draft_writer": "claude-sonnet-5"` |
| Gemini 3.1 Pro (preview) | Google | `gemini-3.1-pro-preview` | 2.000 | 12.00* | $0.040 | 34.96 | yes, tested | **good** | `"draft_writer": "gemini-3.1-pro-preview"` |
| GPT-5.6 Terra (OpenAI) | OpenAI | `gpt-5.6-terra` | 2.000 | 12.00 | $0.044 | 37.93 | needs adapter change | **best** | `"draft_writer": "gpt-5.6-terra"` |

### editor_in_chief

Polishes the draft without adding facts and sets the final status. Faithfulness more than creativity.

Big plan: 1 call(s), 1,890 tokens sent and 800 answered (measured per call with gemini-2.5-flash: 1,400 tokens; measured with gemini-2.5-flash: 1,300 to 1,500).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0.0007 | 0.65 | yes, tested | **ok** | `"editor_in_chief": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40 | $0.0009 | 0.78 | needs adapter change | **ok** | `"editor_in_chief": "gpt-5-nano"` |
| Gemini 2.5 Flash-Lite | Google | `gemini-2.5-flash-lite` | 0.100 | 0.40 | $0.0005 | 0.44 | yes, tested | **ok** | `"editor_in_chief": "gemini-2.5-flash-lite"` |
| GPT-4.1 nano (OpenAI) | OpenAI | `gpt-4.1-nano` | 0.100 | 0.40 | $0.0005 | 0.44 | should (no key to test) | **ok** | `"editor_in_chief": "gpt-4.1-nano"` |
| Ministral 3 14B (Mistral) | Mistral | `ministral-3-14b-25-12` | 0.200 | 0.20 | $0.0005 | 0.47 | should (no key to test) | **ok** | `"editor_in_chief": "ministral-3-14b-25-12"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0.0015 | 1.29 | yes, tested | **good** | `"editor_in_chief": "openai/gpt-oss-120b"` |
| Mistral Small 4 (Mistral) | Mistral | `mistral-small-4-0-26-03` | 0.150 | 0.60 | $0.0008 | 0.66 | should (no key to test) | **good** | `"editor_in_chief": "mistral-small-4-0-26-03"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0.0023 | 2.00 | needs adapter change | **good** | `"editor_in_chief": "gpt-5.6-luna"` |
| DeepSeek Flash (DeepSeek) | DeepSeek | `deepseek-flash` | 0.300 | 1.20* | $0.0015 | 1.33 | needs adapter change | **good** | `"editor_in_chief": "deepseek-flash"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0.0017 | 1.46 | yes, tested | **good** | `"editor_in_chief": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00 | $0.0045 | 3.89 | needs adapter change | **good** | `"editor_in_chief": "gpt-5-mini"` |
| GPT-4.1 mini (OpenAI) | OpenAI | `gpt-4.1-mini` | 0.400 | 1.60 | $0.0020 | 1.77 | should (no key to test) | **good** | `"editor_in_chief": "gpt-4.1-mini"` |
| Mistral Large 3 (Mistral) | Mistral | `mistral-large-3-25-12` | 0.500 | 1.50 | $0.0021 | 1.87 | should (no key to test) | **good** | `"editor_in_chief": "mistral-large-3-25-12"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0.0026 | 2.26 | yes, tested | **good** | `"editor_in_chief": "gemini-3.5-flash-lite"` |
| Gemini 2.5 Flash | Google | `gemini-2.5-flash` | 0.300 | 2.50 | $0.0028 | 2.41 | yes, tested | **good** | `"editor_in_chief": "gemini-2.5-flash"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0.0048 | 4.22 | yes, tested | **good** | `"editor_in_chief": "gemini-3.6-flash"` |
| Gemini 3.7 Flash | Google | `gemini-3.7-flash` | 0.750 | 3.75* | $0.0048 | 4.22 | yes, tested | **good** | `"editor_in_chief": "gemini-3.7-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0.0048 | 4.22 | yes, tested | **best** | `"editor_in_chief": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0.0086 | 7.50 | needs adapter change | **good** | `"editor_in_chief": "gpt-5.4-mini"` |
| DeepSeek V4 Pro (DeepSeek) | DeepSeek | `deepseek-v4-pro` | 1.320 | 3.96* | $0.0057 | 4.93 | needs adapter change | **good** | `"editor_in_chief": "deepseek-v4-pro"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0.0059 | 5.13 | needs adapter change | **good** | `"editor_in_chief": "claude-haiku-4-5"` |
| Gemini 3.5 Flash | Google | `gemini-3.5-flash` | 1.500 | 9.00 | $0.011 | 9.63 | yes, tested | **ok** | `"editor_in_chief": "gemini-3.5-flash"` |
| Claude Sonnet 5 (Anthropic) | Anthropic | `claude-sonnet-5` | 2.000 | 10.00 | $0.012 | 10.25 | needs adapter change | **good** | `"editor_in_chief": "claude-sonnet-5"` |
| Gemini 3.1 Pro (preview) | Google | `gemini-3.1-pro-preview` | 2.000 | 12.00* | $0.015 | 13.45 | yes, tested | **ok** | `"editor_in_chief": "gemini-3.1-pro-preview"` |
| GPT-5.6 Terra (OpenAI) | OpenAI | `gpt-5.6-terra` | 2.000 | 12.00 | $0.023 | 20.00 | needs adapter change | **good** | `"editor_in_chief": "gpt-5.6-terra"` |

### answer_checker

Reads the user's reply to a question: an answer, a yes or a no, not an answer, or stop. Short, any language, latency matters.

Big plan: 0 call(s), 0 tokens sent and 0 answered (measured per call with gemini-2.5-flash: 1,200 tokens; measured with gemini-2.5-flash: about 1,200).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0 | 0 | yes, tested | **best** | `"answer_checker": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40 | $0 | 0 | needs adapter change | **good** | `"answer_checker": "gpt-5-nano"` |
| Gemini 2.5 Flash-Lite | Google | `gemini-2.5-flash-lite` | 0.100 | 0.40 | $0 | 0 | yes, tested | **best** | `"answer_checker": "gemini-2.5-flash-lite"` |
| GPT-4.1 nano (OpenAI) | OpenAI | `gpt-4.1-nano` | 0.100 | 0.40 | $0 | 0 | should (no key to test) | **best** | `"answer_checker": "gpt-4.1-nano"` |
| Ministral 3 14B (Mistral) | Mistral | `ministral-3-14b-25-12` | 0.200 | 0.20 | $0 | 0 | should (no key to test) | **good** | `"answer_checker": "ministral-3-14b-25-12"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0 | 0 | yes, tested | **good** | `"answer_checker": "openai/gpt-oss-120b"` |
| Mistral Small 4 (Mistral) | Mistral | `mistral-small-4-0-26-03` | 0.150 | 0.60 | $0 | 0 | should (no key to test) | **good** | `"answer_checker": "mistral-small-4-0-26-03"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0 | 0 | needs adapter change | **good** | `"answer_checker": "gpt-5.6-luna"` |
| DeepSeek Flash (DeepSeek) | DeepSeek | `deepseek-flash` | 0.300 | 1.20* | $0 | 0 | needs adapter change | **good** | `"answer_checker": "deepseek-flash"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0 | 0 | yes, tested | **best** | `"answer_checker": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00 | $0 | 0 | needs adapter change | **ok** | `"answer_checker": "gpt-5-mini"` |
| GPT-4.1 mini (OpenAI) | OpenAI | `gpt-4.1-mini` | 0.400 | 1.60 | $0 | 0 | should (no key to test) | **good** | `"answer_checker": "gpt-4.1-mini"` |
| Mistral Large 3 (Mistral) | Mistral | `mistral-large-3-25-12` | 0.500 | 1.50 | $0 | 0 | should (no key to test) | **ok** | `"answer_checker": "mistral-large-3-25-12"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0 | 0 | yes, tested | **best** | `"answer_checker": "gemini-3.5-flash-lite"` |
| Gemini 2.5 Flash | Google | `gemini-2.5-flash` | 0.300 | 2.50 | $0 | 0 | yes, tested | **ok** | `"answer_checker": "gemini-2.5-flash"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0 | 0 | yes, tested | **ok** | `"answer_checker": "gemini-3.6-flash"` |
| Gemini 3.7 Flash | Google | `gemini-3.7-flash` | 0.750 | 3.75* | $0 | 0 | yes, tested | **ok** | `"answer_checker": "gemini-3.7-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0 | 0 | yes, tested | **ok** | `"answer_checker": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0 | 0 | needs adapter change | **ok** | `"answer_checker": "gpt-5.4-mini"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0 | 0 | needs adapter change | **ok** | `"answer_checker": "claude-haiku-4-5"` |

### user_clarification

Writes a short friendly question for the user. Trivial.

Big plan: 0 call(s), 0 tokens sent and 0 answered (measured per call with gemini-2.5-flash: 130 tokens; measured with gemini-2.5-flash: about 130).

| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |
|---|---|---|---|---|---|---|---|---|---|
| GPT-OSS 20B (Groq) | Groq | `openai/gpt-oss-20b` | 0.075 | 0.30 | $0 | 0 | yes, tested | **best** | `"user_clarification": "openai/gpt-oss-20b"` |
| GPT-5 nano (OpenAI) | OpenAI | `gpt-5-nano` | 0.050 | 0.40 | $0 | 0 | needs adapter change | **good** | `"user_clarification": "gpt-5-nano"` |
| Gemini 2.5 Flash-Lite | Google | `gemini-2.5-flash-lite` | 0.100 | 0.40 | $0 | 0 | yes, tested | **best** | `"user_clarification": "gemini-2.5-flash-lite"` |
| GPT-4.1 nano (OpenAI) | OpenAI | `gpt-4.1-nano` | 0.100 | 0.40 | $0 | 0 | should (no key to test) | **best** | `"user_clarification": "gpt-4.1-nano"` |
| Ministral 3 14B (Mistral) | Mistral | `ministral-3-14b-25-12` | 0.200 | 0.20 | $0 | 0 | should (no key to test) | **best** | `"user_clarification": "ministral-3-14b-25-12"` |
| GPT-OSS 120B (Groq) | Groq | `openai/gpt-oss-120b` | 0.150 | 0.60 | $0 | 0 | yes, tested | **good** | `"user_clarification": "openai/gpt-oss-120b"` |
| Mistral Small 4 (Mistral) | Mistral | `mistral-small-4-0-26-03` | 0.150 | 0.60 | $0 | 0 | should (no key to test) | **best** | `"user_clarification": "mistral-small-4-0-26-03"` |
| GPT-5.6 Luna (OpenAI) | OpenAI | `gpt-5.6-luna` | 0.200 | 1.20 | $0 | 0 | needs adapter change | **best** | `"user_clarification": "gpt-5.6-luna"` |
| DeepSeek Flash (DeepSeek) | DeepSeek | `deepseek-flash` | 0.300 | 1.20* | $0 | 0 | needs adapter change | **good** | `"user_clarification": "deepseek-flash"` |
| Gemini 3.1 Flash-Lite | Google | `gemini-3.1-flash-lite` | 0.250 | 1.50 | $0 | 0 | yes, tested | **best** | `"user_clarification": "gemini-3.1-flash-lite"` |
| GPT-5 mini (OpenAI) | OpenAI | `gpt-5-mini` | 0.250 | 2.00 | $0 | 0 | needs adapter change | **ok** | `"user_clarification": "gpt-5-mini"` |
| GPT-4.1 mini (OpenAI) | OpenAI | `gpt-4.1-mini` | 0.400 | 1.60 | $0 | 0 | should (no key to test) | **best** | `"user_clarification": "gpt-4.1-mini"` |
| Mistral Large 3 (Mistral) | Mistral | `mistral-large-3-25-12` | 0.500 | 1.50 | $0 | 0 | should (no key to test) | **ok** | `"user_clarification": "mistral-large-3-25-12"` |
| Gemini 3.5 Flash-Lite | Google | `gemini-3.5-flash-lite` | 0.300 | 2.50 | $0 | 0 | yes, tested | **best** | `"user_clarification": "gemini-3.5-flash-lite"` |
| Gemini 2.5 Flash | Google | `gemini-2.5-flash` | 0.300 | 2.50 | $0 | 0 | yes, tested | **ok** | `"user_clarification": "gemini-2.5-flash"` |
| Gemini 3.6 Flash | Google | `gemini-3.6-flash` | 0.750 | 3.75* | $0 | 0 | yes, tested | **ok** | `"user_clarification": "gemini-3.6-flash"` |
| Gemini 3.7 Flash | Google | `gemini-3.7-flash` | 0.750 | 3.75* | $0 | 0 | yes, tested | **ok** | `"user_clarification": "gemini-3.7-flash"` |
| Gemini 3.8 Flash | Google | `gemini-3.8-flash` | 0.750 | 3.75* | $0 | 0 | yes, tested | **ok** | `"user_clarification": "gemini-3.8-flash"` |
| GPT-5.4 mini (OpenAI) | OpenAI | `gpt-5.4-mini` | 0.750 | 4.50 | $0 | 0 | needs adapter change | **ok** | `"user_clarification": "gpt-5.4-mini"` |
| Claude Haiku 4.5 (Anthropic) | Anthropic | `claude-haiku-4-5` | 1.000 | 5.00 | $0 | 0 | needs adapter change | **good** | `"user_clarification": "claude-haiku-4-5"` |

## 5. How to choose

1. One profile for every step: `windows\Scripts\python.exe tests\manual\show_models.py --profile=budget50`.
2. One step: `windows\Scripts\python.exe tests\manual\show_models.py --set=project_manager=openai/gpt-oss-120b` (or write the line of the table in `steps` of `config/step_models.json`). Only models the agent's provider table knows can be chosen (`domain/value_objects/model_catalog.py`).
3. See what is in use with its price: `windows\Scripts\python.exe tests\manual\show_models.py`.
4. Before you trust a model on a step: `tests/manual/debug_flow.py --real`, then `--only=<step> --state=<file> --repeat=5`. The problems it finds and `compare.md` show if the model is steady.
5. To change the budget, the rate or the size of the plans: `config/budget.json`, then `show_models.py --budget`.
