# application/system_prompts/

Builds the **system message** every LLM step sends.

| File | Contents |
|---|---|
| `general.py` | `build_system_prompt_from_file(prompt_file, clock, override, step_text)` joins, in this order: the generic rules (`prompts/0_generic_prompt.txt`), what the robot can and cannot do (`prompts/capabilities.txt`), `CURRENT DATE AND TIME: ...` (from `application/support/clock.py`) and the step's own prompt. `build_system_prompt(phase)` and `LoadSystemPrompt(phase)` do the same by phase number; `prompt_file_of` looks the file up in `runtime/step/catalog.py`. |

## How it works in the project

- `PhaseRunner` (`runtime/step/runner.py`) calls `build_system_prompt_from_file` for each call. The profile may change the step's part with a `PromptOverride` (`prompt_replace` / `prompt_append`, `support/llm/prompt_overrides.py`); the generic rules, the capabilities and the date always stay in front.
- The step's prompt text normally comes from the configuration source (`Agent.step_prompts`); with no text it is read from the repository.
- Files are resolved from the project root, not from the working directory.
- The prompt files live in `prompts/` at the project root. A change to a prompt changes the golden file (`UPDATE_GOLDEN=1`, on purpose) and needs `docs/rules/schemas-and-prompts.md` updated.
