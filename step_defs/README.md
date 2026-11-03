# step_defs/

One JSON declaration per step: its kind, prompt, answer pieces, `reads` and `writes` (PR-005 section 3.2). Named `step_defs` so it does not share a name with `application/steps/`, which holds the Python of the steps.

Filled in T-05.16: the ten LLM steps (`kind` `llm` or `llm_per_action`) and the three code steps. A declaration has:

| Key | Meaning |
|---|---|
| `kind`, `legacy_id`, `group` | `llm`, `llm_per_action` or `code`; the old phase number and the family it sorts with (labels) |
| `prompt.file`, `default_models`, `intent`, `format_name` | the prompt (a file of `prompts/`), the model when a profile says nothing, the intent label of the call and the name of the answer format |
| `answer` | `pieces` (`{name, file, key}` of existing pieces of `schema/response/`) and `required`; or a whole `schema` / `schema_file` |
| `reads`, `writes` | fields of `config/state_fields.json` only; `"field?"` may be missing, `{"key": "field"}` renames what the model is told; `write_always` |
| `functions` | `input`, `apply`, `extra`: names of `application/steps/functions.py`, only when the plain lists are not enough |
| `for_each` | `"actions"` for a step run once per action |
| `function` | for a `code` step: the Python step it runs |
| `data` | reserved for the data policy; nothing reads it |

See `docs/architecture/architecture.md` section 5.1. `python scripts/check_agent.py` checks every file. A new step is one file here and its prompt.
