# application/runtime/step/library/

The steps whose behaviour is **Python code**, grouped by the flow that uses them. (Until 2026-11 this folder was `steps/`, and before that `phases/`.)

| Folder | Contents |
|---|---|
| [`common/`](common/README.md) | The two prompts the runtime itself runs when a flow pauses: answer checker and user clarification. |
| [`special/`](special/README.md) | The action executor (runs planned actions, with MCP tools). |
| [`movement/`](movement/README.md) | The motion validator (arm movements safety net). |
| [`expression/`](expression/README.md) | The gesture builder (random arm gesture for an emotion). |

## Conventions

- A step file declares constants at the top (`PHASE_ID`, `STEP_NAME`, `DEFAULT_MODEL`, `PROMPT_FILE`, `LLM`; the numbers are labels) and then calls `register_step(__name__, "llm" | "code")` from `runtime/step/registry.py`.
- The **folder name is the group** (`common`, `special`, `movement`, `expression`); it fixes the order of the catalog.
- A library step never imports the runner or a flow.
- Steps that are only an LLM call are **not here**: they are declarations in `step_defs/`.
