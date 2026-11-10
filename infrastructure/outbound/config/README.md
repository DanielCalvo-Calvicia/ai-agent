# infrastructure/outbound/config/

Where the agent's **configuration is read from**.

| File | Contents |
|---|---|
| `file_source.py` | `FileConfigSource(root)` implements `ConfigSourcePort`: reads `profiles/`, `flows/`, `step_defs/` and `model_sets/` (one JSON file each), the field catalog `config/state_fields.json` and the prompt files. A folder or file whose name starts with `_` is not loaded (for example `profiles/_unverified/`). A file that cannot be read is reported by name in `Loaded.errors`; the others still load. |

## How it works in the project

`application/assembly/config_snapshot.py` calls the source once at start; `assemble()` checks what it returns. The data is plain (no Python inside a file), so another source (a database, a remote store) could replace this class without touching the application.
