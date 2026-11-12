# application/runtime/

The **path of a message**, top to bottom. This is where ai-agent decides what to do.

```text
profile  ->  flow  ->  step  ->  state
 (one run)  (ordered steps)  (one LLM call or one piece of code)  (what travels between steps)
```

A level uses only the levels below it (`tests/test_orchestration_layout.py`):

| Folder | Level | Answers the question |
|---|---|---|
| [`profile/`](profile/README.md) | 1 | Which profile runs, may the client use it, which inputs does it take? `ProfileRunner` runs **one profile** per message. |
| [`flow/`](flow/README.md) | 2 | In what order do the steps run, when does the flow stop to ask the user, how is its result built? `Pipeline`. |
| [`step/`](step/README.md) | 3 | What does one step do? `PhaseRunner` builds the only LLM payload; declarations and code steps are found through a registry. |
| [`state/`](state/README.md) | 4 | What data does a run carry (`FlowState` and its subclasses), what does a paused run keep, what does a session remember? |

## Key ideas

- **A request runs ONE profile**; a profile names one flow (`profiles/<name>.json` -> `flows/<name>.json`). The service does not route between flows: the client (Brain) chains profiles (`identification`, then the profile that answers, then `gesture`).
- A flow is **data** (a JSON file). The runtime never names the steps of a particular flow: the flow file names them and the registry finds them.
- LLM steps are **declarations** (`step_defs/<name>.json`); only code steps are Python (`step/library/`).
- `runtime/profile/assembled.py` holds `Agent` and `AssembledProfile`, what `assembly/` builds. The runtime never imports `assembly/`, which only runs at start.

See [`docs/architecture/architecture.md`](../../docs/architecture/architecture.md) sections 3 and 4.
