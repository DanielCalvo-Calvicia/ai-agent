# full-examples/

One example per configuration folder with **every key it may hold** in a single object, the way `schema/response/general/full.schema.json` shows the whole answer. Every key has a `//` comment that says what it is, what it is used for, where the code reads it and what to watch out for (also written for an LLM that has to edit the real files). They are **for reading only**:

- They show **every key and every possible value**, even the ones nothing uses today: each file holds one object per possible shape (an array: a profile with `flow` and one with `steps`; a flow that can ask and one that cannot; the five shapes of a step declaration; five servers of different types) and lists all the allowed values (model ids, step names, state fields, schema pieces, hooks, groups) in comments.
- They are `.jsonc` (JSON with comments). The real files are **plain JSON and cannot hold comments** (use a key that starts with `_` for a note). Do not copy an example as it is.
- Nothing loads them (they are outside `flows/`, `mcps/`, `model_sets/`, `profiles/`, `step_defs/`) and they are **not valid configuration as they are**: some keys exclude each other (`flow` / `steps`, the three forms of `answer`) or belong to one kind of step. The comments say which.
- The README of each folder is the full description; if an example and the code disagree, the code is right.

| Example | Real files | Description |
|---|---|---|
| [`flows.full.example.jsonc`](flows.full.example.jsonc) | `flows/<name>.json` | [flows/README.md](../../../flows/README.md) |
| [`mcps.full.example.jsonc`](mcps.full.example.jsonc) | `mcps/*.json` | [mcps/README.md](../../../mcps/README.md) |
| [`model_sets.full.example.jsonc`](model_sets.full.example.jsonc) | `model_sets/<name>.json` | [model_sets/README.md](../../../model_sets/README.md) |
| [`profiles.full.example.jsonc`](profiles.full.example.jsonc) | `profiles/<name>.json` | [profiles/README.md](../../../profiles/README.md) |
| [`step_defs.full.example.jsonc`](step_defs.full.example.jsonc) | `step_defs/<name>.json` | [step_defs/README.md](../../../step_defs/README.md) |

When a key is added to or removed from one of the formats, update its example in the same change.
