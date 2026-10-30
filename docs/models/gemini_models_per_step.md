# Gemini models for each step

_Generated from `config/gemini_models.json` by `tests/manual/show_models.py --write`. Edit that file, not this one._

- Prices and status: Google's pages ai.google.dev/gemini-api/docs/pricing, /models and /thinking, read on 2026-09-21; the prices and the list of models were checked again on 2026-10-27 (T-02.6). Prices are USD per 1M tokens, text, standard paid tier, and the output price includes thinking tokens. Check the page before you rely on a number.
- 'api_check' is the result of one tiny test call per model id through the OpenAI-compatible endpoint (GOOGLE_URL) with the key of this project, on 2026-09-21. It proves the id works with this key, not that the model is good at a step. Re-checked on 2026-10-28 (T-02.3, only the ids that have a free tier): gemini-3.1-flash-lite, gemini-3.5-flash-lite and gemini-3.6-flash answered; gemini-3.8-flash got a 503 "high demand" (a temporary capacity problem, so it keeps its answer of 2026-09-21); gemini-3.1-pro-preview was not called (no free tier). gemini-2.5-flash and gemini-2.5-flash-lite answered 404 "no longer available to new users" and were removed. Later the same day gemini-3-flash-preview answered a test call (1.6 s) and was added. gemini-4-argon was added without a call: it has no free tier, so calling it would cost money; its api_check says "not called" and the tables mark it as untested.
- The ratings are estimates from the tier and Google's description, NOT measurements. Of the Google models only gemini-3.1-flash-lite and gemini-3.8-flash have an end-to-end run in this project (2026-09-21, config/measured_runs.json). Measure a model on a step with: tests/manual/debug_flow.py --only=<step> --state=<file> --repeat=5 --real (see docs/guides/debugging_the_flow.md).
- Sorted from the lowest to the highest cost. blended cost = (3 x input + 1 x output) / 4 per 1M tokens: the calls of this agent send about three times more tokens than they get back. The list is sorted by it, cheapest first.
- Ratings: **best** = the right model for this step; **good** = works well, a fair price for the job; **ok** = works, but slower, weaker or more expensive than needed; **weak** = likely to fail or to give poor results here; **avoid** = wasteful (too expensive or too slow for what the step does).

## 1. Choose the model of each step (summary)

For each step: what it uses now, and the options. Costs are per call of that step (blended price x the tokens of one call, see section 3).

| Step | Uses now | Tokens per call | Cheapest rated best | Cheapest rated good or best | Strongest |
|---|---|---|---|---|---|
| triage_specialist | `gemini-3.1-flash-lite` | 1,650 | `gemini-3.1-flash-lite` $0.0009 | `gemini-3.1-flash-lite` $0.0009 | `gemini-3.5-flash-lite` $0.0014 |
| project_manager | `gemini-3.1-flash-lite` | 2,150 | `gemini-3.8-flash` $0.0032 | `gemini-3.6-flash` $0.0032 | `gemini-3.1-pro-preview` $0.0097 |
| safety_quality_gatekeeper | `gemini-3.1-flash-lite` | 1,500 | none | `gemini-3.1-flash-lite` $0.0008 | `gemini-3.1-pro-preview` $0.0067 |
| cognitive_worker | `gemini-3.1-flash-lite` | 1,270 | `gemini-3.6-flash` $0.0019 | `gemini-3.1-flash-lite` $0.0007 | `gemini-3.8-flash` $0.0019 |
| mcp_operator | `gemini-3.1-flash-lite` | 1,600 | `gemini-3.8-flash` $0.0024 | `gemini-3.1-flash-lite` $0.0009 | `gemini-3.8-flash` $0.0024 |
| data_engineer | `gemini-3.1-flash-lite` | 1,100 | `gemini-3.1-flash-lite` $0.0006 | `gemini-3.1-flash-lite` $0.0006 | `gemini-3.1-flash-lite` $0.0006 |
| draft_writer | `gemini-3.1-flash-lite` | 1,150 | `gemini-3.6-flash` $0.0017 | `gemini-3.1-flash-lite` $0.0006 | `gemini-3.8-flash` $0.0017 |
| editor_in_chief | `gemini-3.1-flash-lite` | 1,400 | `gemini-3.8-flash` $0.0021 | `gemini-3.1-flash-lite` $0.0008 | `gemini-3.8-flash` $0.0021 |
| answer_checker | `gemini-3.1-flash-lite` | 1,200 | `gemini-3.1-flash-lite` $0.0007 | `gemini-3.1-flash-lite` $0.0007 | `gemini-3.5-flash-lite` $0.0010 |
| user_clarification | `gemini-3.1-flash-lite` | 130 | `gemini-3.1-flash-lite` $0.0001 | `gemini-3.1-flash-lite` $0.0001 | `gemini-3.5-flash-lite` $0.0001 |

To use a model for a step, put its id in `steps` of `config/step_models.json`, or run `windows\Scripts\python.exe tests\manual\show_models.py --set=<step>=<model id>`. The exact line for every model is in the table of its step (section 3).

## 2. The models and their cost

| # | Name | Model id | Input $/1M | Output $/1M | Blended $/1M | $ per message | Status | Test call | Thinking |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Gemini 3.1 Flash-Lite | `gemini-3.1-flash-lite` | 0.25 | 1.50 | $0.56 | $0.0056 | stable | answered | not stated in the pages read |
| 2 | Gemini 3.5 Flash-Lite | `gemini-3.5-flash-lite` | 0.30 | 2.50 | $0.85 | $0.0085 | stable | answered | minimal by default |
| 3 | Gemini 3 Flash (preview) | `gemini-3-flash-preview` | 0.50 | 3.00 | $1.12 | $0.011 | preview | answered | a test call used 20 thinking tokens (2026-10-28); not stated in the pages read |
| 4 | Gemini 3.6 Flash | `gemini-3.6-flash` | 0.75 | 3.75* | $1.50 | $0.015 | stable | answered | medium by default. Can go down to 'minimal'. |
| 5 | Gemini 3.8 Flash | `gemini-3.8-flash` | 0.75 | 3.75* | $1.50 | $0.015 | stable | answered | medium by default |
| 6 | Gemini 4 Argon | `gemini-4-argon` | 2.00 | 10.00* | $4.00 | $0.040 | stable | not called | not stated in the pages read |
| 7 | Gemini 3.1 Pro (preview) | `gemini-3.1-pro-preview` | 2.00 | 12.00* | $4.50 | $0.045 | preview | answered | always on |

\* Gemini 3.6 Flash: until 2026-12-31. From 2027-01-01: 1.50 in, 7.50 out.
\* Gemini 3.8 Flash: until 2026-12-31. From 2027-01-01: 1.50 in, 7.50 out.
\* Gemini 4 Argon: until 2026-11-30. From 2026-12-01: 4.00 in, 20.00 out.
\* Gemini 3.1 Pro (preview): prompts up to 200k tokens. Above: 4.00 in, 18.00 out.

"$ per message" is the blended cost of about 10,000 tokens (one message of this agent: 6 to 7 calls in a row) if all its calls used that model.

| Name | Summary |
|---|---|
| Gemini 3.1 Flash-Lite | Google: frontier-class performance at reduced cost. |
| Gemini 3.5 Flash-Lite | Google: the fastest and most cost-effective 3.5 model. Costs 20% more input and 67% more output than 3.1 Flash-Lite. |
| Gemini 3 Flash (preview) | Google's Gemini 3 Flash preview: a Flash model priced between the Lite models and 3.6 Flash. It answered a test call on 2026-10-28 in 1.6 s. A preview can change or go away. Ratings are estimates. |
| Gemini 3.6 Flash | Google: balances speed and multimodal capabilities for general tasks. Same price as 3.8. |
| Gemini 3.8 Flash | Google: made for long-horizon software engineering, autonomous agents and complex workflows. The newest Flash, same price as 3.6, so prefer it. |
| Gemini 4 Argon | Google's newest model, listed as stable on 2026-10-27. It has no free tier, so it was NOT called (a call costs money): the API lists it for this key and nothing more is known here. Ratings are estimates from its tier, never measured. |
| Gemini 3.1 Pro (preview) | Google: advanced intelligence for complex problem solving. A preview: it can change, and it has no free tier. |

## 3. One table per step

Each table lists every model, cheapest first, with its cost for a call of that step and how it should perform there. `Tokens per call` is what a call of the step used with gemini-2.5-flash in the real runs (input plus output, thinking included); other models will use somewhat different amounts, and the steps marked *estimate* were not measured.

### triage_specialist

Classifies the request into a small JSON. Runs first, so latency matters. Little reasoning, but it must not ask for details it does not need.

- Tokens per call: about **1,650** (measured with gemini-2.5-flash: 1,500 to 1,700). Calls per message: 1 per message.
- Uses now: `gemini-3.1-flash-lite`.

| Model | Model id | Input $/1M | Output $/1M | $ per call | $ per 1,000 calls | Rating | Why | Use it |
|---|---|---|---|---|---|---|---|---|
| Gemini 3.1 Flash-Lite | `gemini-3.1-flash-lite` | 0.25 | 1.50 | $0.0009 | $0.93 | **best** | Cheap and capable classifier. | `"triage_specialist": "gemini-3.1-flash-lite"` |
| Gemini 3.5 Flash-Lite | `gemini-3.5-flash-lite` | 0.30 | 2.50 | $0.0014 | $1.40 | **best** | Minimal thinking by default: fast. | `"triage_specialist": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | `gemini-3-flash-preview` | 0.50 | 3.00 | $0.0019 | $1.86 | **ok** | Overkill for a classifier; a preview. | `"triage_specialist": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | `gemini-3.6-flash` | 0.75 | 3.75* | $0.0025 | $2.48 | **ok** | Overkill, unless the thinking level is set to minimal. | `"triage_specialist": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | `gemini-3.8-flash` | 0.75 | 3.75* | $0.0025 | $2.48 | **ok** | Overkill. | `"triage_specialist": "gemini-3.8-flash"` |
| Gemini 4 Argon | `gemini-4-argon` | 2.00 | 10.00* | $0.0066 | $6.60 | **avoid** | Wasteful: paid only. | `"triage_specialist": "gemini-4-argon"` |
| Gemini 3.1 Pro (preview) | `gemini-3.1-pro-preview` | 2.00 | 12.00* | $0.0074 | $7.42 | **avoid** | Wasteful. | `"triage_specialist": "gemini-3.1-pro-preview"` |

### project_manager

The hardest step. Builds the plan: a recursive action tree with dependencies, types and tool choice, in a strict schema. Needs real reasoning. One call per message.

- Tokens per call: about **2,150** (measured with gemini-2.5-flash: about 2,150). Calls per message: 1 per message.
- Uses now: `gemini-3.1-flash-lite`.

| Model | Model id | Input $/1M | Output $/1M | $ per call | $ per 1,000 calls | Rating | Why | Use it |
|---|---|---|---|---|---|---|---|---|
| Gemini 3.1 Flash-Lite | `gemini-3.1-flash-lite` | 0.25 | 1.50 | $0.0012 | $1.21 | **ok** | May plan simple requests well. Test before trusting it. | `"project_manager": "gemini-3.1-flash-lite"` |
| Gemini 3.5 Flash-Lite | `gemini-3.5-flash-lite` | 0.30 | 2.50 | $0.0018 | $1.83 | **ok** | Better than 3.1 Flash-Lite is likely, still a lite model. | `"project_manager": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | `gemini-3-flash-preview` | 0.50 | 3.00 | $0.0024 | $2.42 | **ok** | May plan well; a preview and unmeasured. Test before trusting it. | `"project_manager": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | `gemini-3.6-flash` | 0.75 | 3.75* | $0.0032 | $3.23 | **good** | Solid planner. | `"project_manager": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | `gemini-3.8-flash` | 0.75 | 3.75* | $0.0032 | $3.23 | **best** | The best Flash for planning. | `"project_manager": "gemini-3.8-flash"` |
| Gemini 4 Argon | `gemini-4-argon` | 2.00 | 10.00* | $0.0086 | $8.60 | **best** | The newest top model; an estimate from its tier, never run here. | `"project_manager": "gemini-4-argon"` |
| Gemini 3.1 Pro (preview) | `gemini-3.1-pro-preview` | 2.00 | 12.00* | $0.0097 | $9.67 | **best** | The strongest planner, if the plan quality is the problem. | `"project_manager": "gemini-3.1-pro-preview"` |

### safety_quality_gatekeeper

Judges the plan for risk and decides if the user must confirm. Small JSON, judgement more than reasoning. One call.

- Tokens per call: about **1,500** (measured with gemini-2.5-flash: 1,350 to 1,700). Calls per message: 1 per message.
- Uses now: `gemini-3.1-flash-lite`.

| Model | Model id | Input $/1M | Output $/1M | $ per call | $ per 1,000 calls | Rating | Why | Use it |
|---|---|---|---|---|---|---|---|---|
| Gemini 3.1 Flash-Lite | `gemini-3.1-flash-lite` | 0.25 | 1.50 | $0.0008 | $0.84 | **good** | Enough judgement for a yes or no on risk. | `"safety_quality_gatekeeper": "gemini-3.1-flash-lite"` |
| Gemini 3.5 Flash-Lite | `gemini-3.5-flash-lite` | 0.30 | 2.50 | $0.0013 | $1.28 | **good** | Good judgement, fast. | `"safety_quality_gatekeeper": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | `gemini-3-flash-preview` | 0.50 | 3.00 | $0.0017 | $1.69 | **good** | Enough judgement for a yes or no on risk. | `"safety_quality_gatekeeper": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | `gemini-3.6-flash` | 0.75 | 3.75* | $0.0022 | $2.25 | **good** | Solid judgement. | `"safety_quality_gatekeeper": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | `gemini-3.8-flash` | 0.75 | 3.75* | $0.0022 | $2.25 | **good** | Solid judgement. | `"safety_quality_gatekeeper": "gemini-3.8-flash"` |
| Gemini 4 Argon | `gemini-4-argon` | 2.00 | 10.00* | $0.0060 | $6.00 | **good** | Very careful on risk, more than needed. | `"safety_quality_gatekeeper": "gemini-4-argon"` |
| Gemini 3.1 Pro (preview) | `gemini-3.1-pro-preview` | 2.00 | 12.00* | $0.0067 | $6.75 | **good** | Very careful on risk, more than needed. | `"safety_quality_gatekeeper": "gemini-3.1-pro-preview"` |

### cognitive_worker

One call per action of the plan: answers, analyses, writes a piece. The quality of the content comes from here. The number of calls grows with the plan.

- Tokens per call: about **1,270** (measured with gemini-2.5-flash: about 1,270 per action). Calls per message: 1 per action of the plan (1 to 3 is usual).
- Uses now: `gemini-3.1-flash-lite`.

| Model | Model id | Input $/1M | Output $/1M | $ per call | $ per 1,000 calls | Rating | Why | Use it |
|---|---|---|---|---|---|---|---|---|
| Gemini 3.1 Flash-Lite | `gemini-3.1-flash-lite` | 0.25 | 1.50 | $0.0007 | $0.71 | **good** | Good content at a low price. | `"cognitive_worker": "gemini-3.1-flash-lite"` |
| Gemini 3.5 Flash-Lite | `gemini-3.5-flash-lite` | 0.30 | 2.50 | $0.0011 | $1.08 | **good** | Good content. | `"cognitive_worker": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | `gemini-3-flash-preview` | 0.50 | 3.00 | $0.0014 | $1.43 | **good** | Good content for the price. | `"cognitive_worker": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | `gemini-3.6-flash` | 0.75 | 3.75* | $0.0019 | $1.91 | **best** | Strong content. | `"cognitive_worker": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | `gemini-3.8-flash` | 0.75 | 3.75* | $0.0019 | $1.91 | **best** | Strong content. | `"cognitive_worker": "gemini-3.8-flash"` |
| Gemini 4 Argon | `gemini-4-argon` | 2.00 | 10.00* | $0.0051 | $5.08 | **good** | Top content, at a price. | `"cognitive_worker": "gemini-4-argon"` |
| Gemini 3.1 Pro (preview) | `gemini-3.1-pro-preview` | 2.00 | 12.00* | $0.0057 | $5.71 | **good** | Top content, at a price. | `"cognitive_worker": "gemini-3.1-pro-preview"` |

### mcp_operator

One or more calls per tool action. Needs reliable function calling plus a valid JSON answer.

- Tokens per call: about **1,600** (estimate, not measured: the tool list makes the prompt longer). Calls per message: 1 to 3 per tool action, 0 when no tool is used.
- Uses now: `gemini-3.1-flash-lite`.

| Model | Model id | Input $/1M | Output $/1M | $ per call | $ per 1,000 calls | Rating | Why | Use it |
|---|---|---|---|---|---|---|---|---|
| Gemini 3.1 Flash-Lite | `gemini-3.1-flash-lite` | 0.25 | 1.50 | $0.0009 | $0.90 | **good** | Function calling should be fine. Test it. | `"mcp_operator": "gemini-3.1-flash-lite"` |
| Gemini 3.5 Flash-Lite | `gemini-3.5-flash-lite` | 0.30 | 2.50 | $0.0014 | $1.36 | **good** | Function calling should be fine. Test it. | `"mcp_operator": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | `gemini-3-flash-preview` | 0.50 | 3.00 | $0.0018 | $1.80 | **good** | Function calling should be fine. Test it. | `"mcp_operator": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | `gemini-3.6-flash` | 0.75 | 3.75* | $0.0024 | $2.40 | **good** | Good tool use. | `"mcp_operator": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | `gemini-3.8-flash` | 0.75 | 3.75* | $0.0024 | $2.40 | **best** | Built for agents and tools. | `"mcp_operator": "gemini-3.8-flash"` |
| Gemini 4 Argon | `gemini-4-argon` | 2.00 | 10.00* | $0.0064 | $6.40 | **good** | Top tool use, at a price. | `"mcp_operator": "gemini-4-argon"` |
| Gemini 3.1 Pro (preview) | `gemini-3.1-pro-preview` | 2.00 | 12.00* | $0.0072 | $7.20 | **good** | Top tool use, at a price. | `"mcp_operator": "gemini-3.1-pro-preview"` |

### data_engineer

Cleans the output of a tool. Mechanical: precision, no creativity.

- Tokens per call: about **1,100** (estimate, not measured). Calls per message: 1 per tool result, 0 when no tool is used.
- Uses now: `gemini-3.1-flash-lite`.

| Model | Model id | Input $/1M | Output $/1M | $ per call | $ per 1,000 calls | Rating | Why | Use it |
|---|---|---|---|---|---|---|---|---|
| Gemini 3.1 Flash-Lite | `gemini-3.1-flash-lite` | 0.25 | 1.50 | $0.0006 | $0.62 | **best** | Cheap and precise enough. | `"data_engineer": "gemini-3.1-flash-lite"` |
| Gemini 3.5 Flash-Lite | `gemini-3.5-flash-lite` | 0.30 | 2.50 | $0.0009 | $0.93 | **good** | More than needed. | `"data_engineer": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | `gemini-3-flash-preview` | 0.50 | 3.00 | $0.0012 | $1.24 | **ok** | Overkill. | `"data_engineer": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | `gemini-3.6-flash` | 0.75 | 3.75* | $0.0016 | $1.65 | **ok** | Overkill. | `"data_engineer": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | `gemini-3.8-flash` | 0.75 | 3.75* | $0.0016 | $1.65 | **ok** | Overkill. | `"data_engineer": "gemini-3.8-flash"` |
| Gemini 4 Argon | `gemini-4-argon` | 2.00 | 10.00* | $0.0044 | $4.40 | **avoid** | Wasteful. | `"data_engineer": "gemini-4-argon"` |
| Gemini 3.1 Pro (preview) | `gemini-3.1-pro-preview` | 2.00 | 12.00* | $0.0050 | $4.95 | **avoid** | Wasteful. | `"data_engineer": "gemini-3.1-pro-preview"` |

### draft_writer

Writes the first answer for the user from all the outputs. Writing quality and following the constraints.

- Tokens per call: about **1,150** (measured with gemini-2.5-flash: about 1,150). Calls per message: 1 per message.
- Uses now: `gemini-3.1-flash-lite`.

| Model | Model id | Input $/1M | Output $/1M | $ per call | $ per 1,000 calls | Rating | Why | Use it |
|---|---|---|---|---|---|---|---|---|
| Gemini 3.1 Flash-Lite | `gemini-3.1-flash-lite` | 0.25 | 1.50 | $0.0006 | $0.65 | **good** | Good writing for the price. | `"draft_writer": "gemini-3.1-flash-lite"` |
| Gemini 3.5 Flash-Lite | `gemini-3.5-flash-lite` | 0.30 | 2.50 | $0.0010 | $0.98 | **good** | Good writing. | `"draft_writer": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | `gemini-3-flash-preview` | 0.50 | 3.00 | $0.0013 | $1.29 | **good** | Good writing for the price. | `"draft_writer": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | `gemini-3.6-flash` | 0.75 | 3.75* | $0.0017 | $1.72 | **best** | Strong writing. | `"draft_writer": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | `gemini-3.8-flash` | 0.75 | 3.75* | $0.0017 | $1.72 | **best** | Strong writing. | `"draft_writer": "gemini-3.8-flash"` |
| Gemini 4 Argon | `gemini-4-argon` | 2.00 | 10.00* | $0.0046 | $4.60 | **good** | Top writing, at a price. | `"draft_writer": "gemini-4-argon"` |
| Gemini 3.1 Pro (preview) | `gemini-3.1-pro-preview` | 2.00 | 12.00* | $0.0052 | $5.17 | **good** | Top writing, at a price. | `"draft_writer": "gemini-3.1-pro-preview"` |

### editor_in_chief

Polishes the draft without adding facts and sets the final status. Faithfulness more than creativity.

- Tokens per call: about **1,400** (measured with gemini-2.5-flash: 1,300 to 1,500). Calls per message: 1 per message.
- Uses now: `gemini-3.1-flash-lite`.

| Model | Model id | Input $/1M | Output $/1M | $ per call | $ per 1,000 calls | Rating | Why | Use it |
|---|---|---|---|---|---|---|---|---|
| Gemini 3.1 Flash-Lite | `gemini-3.1-flash-lite` | 0.25 | 1.50 | $0.0008 | $0.79 | **good** | Good polishing. | `"editor_in_chief": "gemini-3.1-flash-lite"` |
| Gemini 3.5 Flash-Lite | `gemini-3.5-flash-lite` | 0.30 | 2.50 | $0.0012 | $1.19 | **good** | Good polishing. | `"editor_in_chief": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | `gemini-3-flash-preview` | 0.50 | 3.00 | $0.0016 | $1.57 | **good** | Good polishing. | `"editor_in_chief": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | `gemini-3.6-flash` | 0.75 | 3.75* | $0.0021 | $2.10 | **good** | Good polishing. | `"editor_in_chief": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | `gemini-3.8-flash` | 0.75 | 3.75* | $0.0021 | $2.10 | **best** | Faithful, clean polishing. | `"editor_in_chief": "gemini-3.8-flash"` |
| Gemini 4 Argon | `gemini-4-argon` | 2.00 | 10.00* | $0.0056 | $5.60 | **ok** | Overkill. | `"editor_in_chief": "gemini-4-argon"` |
| Gemini 3.1 Pro (preview) | `gemini-3.1-pro-preview` | 2.00 | 12.00* | $0.0063 | $6.30 | **ok** | Overkill. | `"editor_in_chief": "gemini-3.1-pro-preview"` |

### answer_checker

Reads the user's reply to a question: an answer, a yes or a no, not an answer, or stop. Short, any language, latency matters.

- Tokens per call: about **1,200** (measured with gemini-2.5-flash: about 1,200). Calls per message: 1 per reply to a question of the agent, 0 otherwise.
- Uses now: `gemini-3.1-flash-lite`.

| Model | Model id | Input $/1M | Output $/1M | $ per call | $ per 1,000 calls | Rating | Why | Use it |
|---|---|---|---|---|---|---|---|---|
| Gemini 3.1 Flash-Lite | `gemini-3.1-flash-lite` | 0.25 | 1.50 | $0.0007 | $0.68 | **best** | Short and cheap. | `"answer_checker": "gemini-3.1-flash-lite"` |
| Gemini 3.5 Flash-Lite | `gemini-3.5-flash-lite` | 0.30 | 2.50 | $0.0010 | $1.02 | **best** | Fast, multilingual. | `"answer_checker": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | `gemini-3-flash-preview` | 0.50 | 3.00 | $0.0014 | $1.35 | **ok** | Overkill. | `"answer_checker": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | `gemini-3.6-flash` | 0.75 | 3.75* | $0.0018 | $1.80 | **ok** | Overkill. | `"answer_checker": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | `gemini-3.8-flash` | 0.75 | 3.75* | $0.0018 | $1.80 | **ok** | Overkill. | `"answer_checker": "gemini-3.8-flash"` |
| Gemini 4 Argon | `gemini-4-argon` | 2.00 | 10.00* | $0.0048 | $4.80 | **avoid** | Wasteful. | `"answer_checker": "gemini-4-argon"` |
| Gemini 3.1 Pro (preview) | `gemini-3.1-pro-preview` | 2.00 | 12.00* | $0.0054 | $5.40 | **avoid** | Wasteful. | `"answer_checker": "gemini-3.1-pro-preview"` |

### user_clarification

Writes a short friendly question for the user. Trivial.

- Tokens per call: about **130** (measured with gemini-2.5-flash: about 130). Calls per message: 1 when the agent asks the user, 0 otherwise.
- Uses now: `gemini-3.1-flash-lite`.

| Model | Model id | Input $/1M | Output $/1M | $ per call | $ per 1,000 calls | Rating | Why | Use it |
|---|---|---|---|---|---|---|---|---|
| Gemini 3.1 Flash-Lite | `gemini-3.1-flash-lite` | 0.25 | 1.50 | $0.0001 | $0.07 | **best** | Trivial text. | `"user_clarification": "gemini-3.1-flash-lite"` |
| Gemini 3.5 Flash-Lite | `gemini-3.5-flash-lite` | 0.30 | 2.50 | $0.0001 | $0.11 | **best** | Trivial text. | `"user_clarification": "gemini-3.5-flash-lite"` |
| Gemini 3 Flash (preview) | `gemini-3-flash-preview` | 0.50 | 3.00 | $0.0001 | $0.15 | **ok** | Overkill. | `"user_clarification": "gemini-3-flash-preview"` |
| Gemini 3.6 Flash | `gemini-3.6-flash` | 0.75 | 3.75* | $0.0002 | $0.20 | **ok** | Overkill. | `"user_clarification": "gemini-3.6-flash"` |
| Gemini 3.8 Flash | `gemini-3.8-flash` | 0.75 | 3.75* | $0.0002 | $0.20 | **ok** | Overkill. | `"user_clarification": "gemini-3.8-flash"` |
| Gemini 4 Argon | `gemini-4-argon` | 2.00 | 10.00* | $0.0005 | $0.52 | **avoid** | Wasteful. | `"user_clarification": "gemini-4-argon"` |
| Gemini 3.1 Pro (preview) | `gemini-3.1-pro-preview` | 2.00 | 12.00* | $0.0006 | $0.58 | **avoid** | Wasteful. | `"user_clarification": "gemini-3.1-pro-preview"` |

## 4. Profiles in `config/step_models.json`

Active profile: **proven**. `steps` wins over the profile, and `AI_AGENT_MODEL_PHASE_<n>` wins over both.

| Step | proven | budget | balanced | quality | budget50 | claude_sonnet | budget50_groq | google_free | claude_haiku | claude_mixed |
|---|---|---|---|---|---|---|---|---|---|---|
| triage_specialist | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `gemini-3.5-flash-lite` | `gemini-3.1-flash-lite` | `claude-sonnet-5` | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `claude-haiku-4-5` | `claude-haiku-4-5` |
| project_manager | `gemini-3.1-flash-lite` | `gemini-3.5-flash-lite` | `gemini-3.8-flash` | `gemini-3.1-pro-preview` | `gemini-3.5-flash-lite` | `claude-sonnet-5` | `openai/gpt-oss-120b` | `gemini-3.6-flash` | `claude-sonnet-5-5` | `claude-sonnet-5-5` |
| safety_quality_gatekeeper | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `gemini-3.8-flash` | `gemini-3.1-flash-lite` | `claude-sonnet-5` | `openai/gpt-oss-120b` | `gemini-3.6-flash` | `claude-haiku-4-5` | `claude-haiku-4-5` |
| cognitive_worker | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `gemini-3.5-flash-lite` | `gemini-3.8-flash` | `gemini-3.1-flash-lite` | `claude-sonnet-5` | `openai/gpt-oss-120b` | `gemini-3.6-flash` | `claude-haiku-4-5` | `claude-haiku-4-5` |
| mcp_operator | `gemini-3.1-flash-lite` | `gemini-3.5-flash-lite` | `gemini-3.8-flash` | `gemini-3.8-flash` | `gemini-3.1-flash-lite` | `claude-sonnet-5` | `gemini-3.1-flash-lite` | `gemini-3.6-flash` | `claude-haiku-4-5` | `claude-haiku-4-5` |
| data_engineer | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `claude-sonnet-5` | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `claude-haiku-4-5` | `claude-haiku-4-5` |
| draft_writer | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `gemini-3.8-flash` | `gemini-3.8-flash` | `gemini-3.1-flash-lite` | `claude-sonnet-5` | `openai/gpt-oss-120b` | `gemini-3.6-flash` | `claude-haiku-4-5` | `claude-sonnet-5-5` |
| editor_in_chief | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `gemini-3.8-flash` | `gemini-3.1-flash-lite` | `claude-sonnet-5` | `openai/gpt-oss-120b` | `gemini-3.6-flash` | `claude-haiku-4-5` | `claude-sonnet-5-5` |
| answer_checker | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `gemini-3.5-flash-lite` | `gemini-3.1-flash-lite` | `claude-sonnet-5` | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `claude-haiku-4-5` | `claude-haiku-4-5` |
| user_clarification | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `gemini-3.5-flash-lite` | `gemini-3.1-flash-lite` | `claude-sonnet-5` | `gemini-3.1-flash-lite` | `gemini-3.1-flash-lite` | `claude-haiku-4-5` | `claude-haiku-4-5` |

- **proven**: Every step on gemini-3.1-flash-lite, which has an end-to-end run (2026-09-21) and answered a test call on 2026-10-28. It replaces gemini-2.5-flash, the first model tested end to end, which Google no longer gives to new keys. Active since 2026-10-28: on the free tier it answered 10 calls in a row, while gemini-3.6-flash (profile google_free) returned 429 after about 7 calls in 30 s.
- **budget**: The cheapest that should work: gemini-3.1-flash-lite everywhere except the planner and the tool step (gemini-3.5-flash-lite). Untested. It replaces the gemini-2.5-flash-lite and gemini-2.5-flash of the first version, which Google no longer gives to new keys.
- **balanced**: Cheap lite models for the small steps, a stronger Flash for planning, tools and writing. Untested. Prices of 3.6 to 3.8 Flash double on 2027-01-01.
- **quality**: The best plan and the best writing, whatever the price. Untested. gemini-3.1-pro-preview is a preview.
- **budget50**: Fits 50 EUR for 1,000 messages even if every message has a plan of 30 actions. Google models only. gemini-3.1-flash-lite for almost everything (it does not think, so it costs little), gemini-3.5-flash-lite for the planner (the one step that needs reasoning: a Lite model, rated ok). Untested as a combination. It replaces gemini-2.5-flash for the planner and gemini-2.5-flash-lite for three steps, which Google no longer gives to new keys.
- **claude_sonnet**: The same Claude Sonnet model on every step, for the Dynamics MCP epic (T-01). Needs ANTHROPIC_API_KEY. Untested; the id is confirmed in T-01.9. `claude-sonnet-5` is a legacy id (still available on 2026-10-27); the current one is `claude-sonnet-5-5`, which T-01.9 decides. Not the active profile: set `profile` to use it.
- **budget50_groq**: Cheaper than budget50: the planner, the gate, the worker, the draft and the editor use openai/gpt-oss-120b on Groq (strong reasoning at 0.15 in and 0.60 out per 1M tokens, tested end to end). Triage, tools, cleaning, the checker and the question use gemini-3.1-flash-lite. Needs GROQ_API_KEY and GROQ_URL. Untested as a combination.
- **google_free**: Google models only, both with a free tier (no billing needed to run or test). The small steps (triage, cleaning, the checker, the question, the emotion reader) use gemini-3.1-flash-lite; the planner, the gate, the worker, the tool step, the draft, the editor and the motion planner use gemini-3.6-flash (the same price as gemini-3.8-flash, which was the first choice but answered 503 "high demand" on every try of 2026-10-28; change them back when it answers). Needs GOOGLE_API_KEY and GOOGLE_URL only. Untested as a combination. Free-tier content is used by Google to improve its products, and its rate limits are not published on Google's pricing page; with a billed key neither applies, but the price of gemini-3.6-flash doubles on 2027-01-01. Decided in PR-004 (2026-10-27). Not active since 2026-10-28: on the free tier gemini-3.6-flash returned 429 "quota exceeded" after about 7 calls in 30 s, and one message calls it about 6 times; proven (every step on gemini-3.1-flash-lite) is active instead.
- **claude_haiku**: Claude through Anthropic's OpenAI-compatible endpoint (ADR-013): claude-haiku-4-5 on every step, claude-sonnet-5-5 for the planner. Needs ANTHROPIC_API_KEY. Not the active profile. Every call carries a strict, sanitized schema (an action nests at most 3 levels), which adds about 2.8k input tokens to the four actions steps. Claude 5 models think by default and the endpoint hides it, so the cost tables understate the cost of the planner. Untested as a combination until T-03.6.
- **claude_mixed**: Claude through Anthropic's OpenAI-compatible endpoint (ADR-013): claude-haiku-4-5 on every step except the planner, the draft writer and the editor, which use claude-sonnet-5-5. Needs ANTHROPIC_API_KEY. Not the active profile. Run once on 2026-10-28 (T-03.6): three messages, 13 calls, 0 errors, about 6.6 cents, and the greeting that claude_haiku answered with a description got a real reply (one sample). Costs about 2.5 times claude_haiku. The strict, sanitized schema adds about 2.8k input tokens to the four actions steps, and the endpoint hides Claude's thinking, so the cost tables understate the cost of the Sonnet steps.

## 5. How to choose

1. See the options of one step and what it uses now: `windows\Scripts\python.exe tests\manual\show_models.py --step=project_manager`.
2. Choose: `windows\Scripts\python.exe tests\manual\show_models.py --set=project_manager=gemini-3.8-flash` (or write it in `steps` of `config/step_models.json`). To go back to the profile: `--clear=project_manager`. To change every step at once: `--profile=budget` (or `balanced`, `quality`, `proven`).
3. For one run only: the variable `AI_AGENT_MODEL_PHASE_<n>` (n: 1 triage, 2 planner, 3 gate, 4 worker, 5 tools, 6 cleaning, 7 draft, 8 editor, 9 answer checker, 99 question).
4. Try the model on that step before you trust it: run the flow once with `tests/manual/debug_flow.py --real`, then repeat the step with `--only=<step> --state=<file> --repeat=5`. The problems it finds and `compare.md` show if the model is steady.
