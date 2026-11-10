# infrastructure/outbound/usage/

**Usage and cost reporting** of the LLM calls.

| File | Contents |
|---|---|
| `langfuse.py` | `LangfuseUsageReporter` implements `UsageReporterPort`. Sends each user message as a trace and each LLM call as a `generation` named after its step (model, tokens including thinking, cost, tags, `profile` / `flow` / `client` / `profile_hash`) through Langfuse's OpenTelemetry endpoint (OTLP over HTTP/JSON, no package needed). Sends in a background queue; a failed send is logged and dropped and **never breaks a call**. Optionally reports tool calls (name, outcome, duration, tries). |
| `prices.py` | `load_prices` (USD per 1M tokens from `config/gemini_models.json` and `config/other_models.json`), `billed_output_tokens` (answered tokens plus hidden thinking) and `cost_usd` (`None` when a model has no price). |

## Privacy

Langfuse receives **the user's text and the prompts and answers of every call**, not only metadata; use a Langfuse project you trust. Tool arguments and tool answers are never sent. Keys come from the environment; without them nothing is reported. See `docs/operations/monitoring.md` and `docs/security/security.md`.
