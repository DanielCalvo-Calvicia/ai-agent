# prompts/profiles/<profile>/

Prompt files that only one profile uses: a `prompt_replace` or `prompt_append` of a step for that profile (PR-005 section 5). The prompts every profile shares stay in `prompts/`.

Empty: no profile changes a prompt yet (T-05.14 built the mechanism). A profile uses a file here as `"overrides": {"draft_writer": {"prompt_append": {"file": "prompts/profiles/<profile>/draft_writer.txt"}}}`, or writes the text inline; `prompt_replace` takes the same two forms. `python scripts/check_agent.py` refuses a missing file, a step with no prompt and a step the profile's flow does not run.
