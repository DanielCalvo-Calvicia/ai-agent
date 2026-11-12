# runtime/step/library/fast/

The code step of the fast flow (`flows/fast.json`, ADR-019, T-08.5). The two LLM steps of that flow, `tool_selector` and `answer_writer`, are declarations in `step_defs/`.

| File | Step | What it does |
|---|---|---|
| `tool_caller.py` | `tool_caller` (code) | Calls the one read-only tool the selector chose, through the tools port (`support/tools/direct_call.py`), and keeps the answer as the output of the action. No model. A second tool call is refused, a tool that is not read-only is refused, a `generation` action is left for the writer. |

**This folder names no MCP server and no tool** (a test enforces it). What one server means goes in the prompt appends of the profile (`prompts/profiles/<profile>/`).
