# application/support/llm/

Helpers around the LLM calls that are not provider code.

| File | Contents |
|---|---|
| `model_selection.py` | `ModelResolver`, `effective_models`, `check_model_set`: which models answer a step, as an **ordered list** (the first answers, the next ones are the fallback after a lack of capacity, ADR-014). Most specific wins: `flows.<flow>.steps.<step>`, `overrides.<step>`, `flows.<flow>`, `models`, then the step's `DEFAULT_MODEL`. A level is a list of model ids or the name of a model set (`model_sets/<name>.json`). No environment variable chooses a model. |
| `schemas.py` | Loads the JSON Schemas the model must follow from `schema/response/` (`load_schema`, `load_schema_file`, `actions_schema`, `object_schema`); `SchemaRef`. |
| `prompt_overrides.py` | `PromptOverride(replace, append)`: what a profile may do to one step's prompt. The answer schema is never changed. |
| `failure.py` | `AgentFailure`, `classify`, `worth_retrying`, `capacity_problem`, `daily_quota_used_up`, retry settings (`AI_AGENT_MAX_ATTEMPTS`, `AI_AGENT_RETRY_WAIT_SECONDS`, `AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE`), and the **apology templates** (not an LLM call, so they work when the LLM is what failed). Never includes raw error text. |

Used by `runtime/step/runner.py`, `runtime/flow/pipeline.py` and `assembly/assemble.py`.
