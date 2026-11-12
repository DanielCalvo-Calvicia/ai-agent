# application/assembly/

**Start-up only.** Builds the whole agent from the configuration and refuses what cannot work. The runtime never imports anything here.

| File | Contents |
|---|---|
| `config_snapshot.py` | `ConfigSnapshot` / `build_snapshot`: everything the agent is made of (profiles, flows, step declarations, model sets, the field catalog), read **once** through `ConfigSourcePort`. A file that cannot be used is kept in `errors` by kind and name instead of stopping the load. Checks `schema_version`. |
| `assemble.py` | `assemble(snapshot)`: the checks. Unknown names or keys; `flow` xor `steps` in a profile; every step reads only what an input, an initial state or an earlier step provides; a flow has a `result_from`; every model list is valid (a custom schema must pass Claude's rules); the token hash is 64 hex characters; tool names exist; prompts exist. Every problem names its file and key. Returns an `Agent`. |
| `flow_file.py` | `flow_from_file(data, ...)`: turns a flow JSON file into the `Flow` the `Pipeline` runs, looking up steps, conditions and hooks. |

## How it works in the project

At start `composition_root/main.py` reads the snapshot and calls `assemble()`. A profile with a problem is **disabled and logged** (`Configuration problem`, `Profile disabled`) while the others serve. `scripts/check_agent.py` and the tests run it strictly (`Agent.raise_on_errors`).
