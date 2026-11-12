# application/support/

The **shared base** the runtime uses. It sits at the bottom of the dependency chain (above the ports and the DTOs) and uses nothing of the runtime.

| File / folder | Contents |
|---|---|
| `environment.py` | `install(resources, settings)`, `read_text`, `read_json`, `list_files`, `setting(name, default)`: the files that ship with the project and the settings of a run, through `ResourcePort` and `SettingsPort`. The application opens no file and reads no variable itself. |
| `clock.py` | `now_text()`: the date and time (with UTC offset) that goes into every system prompt. |
| `expression_settings.py` | `AI_AGENT_SPEECH_CHARS_PER_SECOND`, `AI_AGENT_EXPRESSION_SEED`; `speech_seconds(reply)`, `new_rng(seed)`. |
| [`llm/`](llm/README.md) | Model selection, schemas, prompt overrides and failures. |
| [`tools/`](tools/README.md) | Helpers for the tree of planned actions and for showing MCP servers to the planner. |
