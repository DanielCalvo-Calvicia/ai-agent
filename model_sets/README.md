# model_sets/

One JSON file per model set: a named table of models that a profile can use at any level (PR-005 section 5). Each entry is an **ordered list**: the first model answers
and the next ones are tried when it is out of capacity (ADR-014).

```text
{ "schema_version": 1, "name": "<same as the file>", "_about": "what it is for",
  "default": ["<model id>", "<fallback id>"],        every step that has no entry of its own
  "project_manager": ["<model id>"] }                 one entry per step that differs; keys that start with _ are comments
```

The ten sets here are the ten tables of the old `config/step_models.json` (T-05.5); `proven` is the one `default`, `identification`, `movement` and `gesture` choose; `chat` chooses `claude_haiku`, `special` and `dynamics` `claude_mixed` (a profile names its set).
A file whose name starts with `_` is not loaded. Rules and the order of precedence: `docs/configuration/environment-variables.md`, section 3.
