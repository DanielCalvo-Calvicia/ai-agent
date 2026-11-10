# application/support/

The **shared base** the runtime uses. It sits at the bottom of the dependency chain and reads only `runtime/step/catalog.py` (for the step tables).

| File / folder | Contents |
|---|---|
| `metrics.py` | `SessionMetrics`, `RequestRecord`, `TokenCount`: one record per LLM call with `profile`, `flow`, `step`, `model`, `client`, tokens, `cost_usd` and `profile_hash`; totals by any key (`total_by`); forwards records to a `UsageReporterPort`. Holds no token, input, tool argument or tool answer. |
| `clock.py` | `now_text()`: the date and time (with UTC offset) that goes into every system prompt. |
| `expression_settings.py` | `AI_AGENT_SPEECH_CHARS_PER_SECOND`, `AI_AGENT_EXPRESSION_SEED`; `speech_seconds(reply)`, `new_rng(seed)`. |
| [`llm/`](llm/README.md) | Model selection, schemas, prompt overrides and failures. |
| [`tools/`](tools/README.md) | Helpers for the tree of planned actions and for showing MCP servers to the planner. |
