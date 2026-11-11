# profiles/

One JSON file per **profile**: what a client asks for (PR-005, `docs/proposals/PR-005-flows-steps-profiles.md`; ADR-015). A request runs **one** profile. A profile names **one flow** ([flows/README.md](../flows/README.md)), the **models** of its steps ([model_sets/README.md](../model_sets/README.md)), the **tools** it may reach ([mcps/README.md](../mcps/README.md)), the **inputs** it accepts, and optional per-step changes (`overrides`). It never contains code or a prompt of its own unless you write one under `overrides`.

Read at start by `infrastructure/outbound/config/file_source.py` and checked by `application/assembly/assemble.py`. A profile with a problem is **disabled and logged**; the others keep serving. `python scripts/check_agent.py` (strict) prints every problem with its file and key: run it before every pull request that touches a profile.

## 1. File rules

- File name = profile name = the `name` inside (`chat.json` holds `"name": "chat"`; a mismatch refuses the file). Use lower case, digits and `_`; that is what a client sends in `profile`.
- UTF-8 JSON object, no comments (use `about` for text people read). Any key that starts with `_` is ignored (a place for notes).
- A file or folder whose name starts with `_` is **not loaded** (`_unverified/` holds ten generic profiles on the `default` flow, waiting for a real run).
- `schema_version` must be the whole number `1`.
- An unknown key is an error (`unknown key 'x'. Keys: ...`), never ignored silently.

## 2. All fields

| Key | Required | Values | Meaning |
|---|---|---|---|
| `schema_version` | yes | `1` | Format version. |
| `name` | yes (always write it) | text, equal to the file name | The public name. |
| `about` | no | text | What the profile is for. Documentation only; not sent to any model. |
| `token_sha256` | yes, **except** for `default` | 64 lowercase hex characters | The SHA-256 of the token a client must send. See section 3. |
| `flow` | one of `flow` / `steps` | name of a file in `flows/` | The ordered steps this profile runs. |
| `steps` | one of `flow` / `steps` | list of steps (same entries as a flow file) | An anonymous flow written in the profile. **Accepted by the check but cannot run yet**: the runner refuses it (`needs steps as files`). Use `flow`. Exactly one of the two must be present. |
| `models` | no | a **model set name** or a **list of model ids** | The models of every step (level 4 of the order below). Without any level, every step uses its own default (a Google model). |
| `tools` | no | `{"servers": [...], "tools": [...]}` | Which MCP tools every step of this profile may use at most. See section 5. |
| `inputs` | no | `{"requires": [...], "accepts": [...]}` | State fields the client may send in `inputs`. See section 4. |
| `default_return` | no | `"text"` (default) or `"full"` | What the answer carries when the request does not say `return`: only the text, or the whole `Response` (classification, actions...). A request's `return` field overrides it. |
| `overrides` | no | `{ "<step>": { ... } }` | Changes for one step in every flow: `models`, `tools`, `prompt_replace`, `prompt_append`. Section 6. |
| `flows` | no | `{ "<flow>": { "models", "tools", "steps": {"<step>": {"models"}} } }` | Changes for one flow, or one step in one flow. Section 6. |
| `settings` | no | `{"history_turns": int, "max_mcp_calls_per_message": int}` | Whole numbers, zero or more. **Checked but not applied yet**: the service still uses `AI_AGENT_HISTORY_TURNS` and `AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE` for every profile. |
| `initial_state` | no | `{ "<state field>": value }` | Field names must be in `config/state_fields.json`. **Checked but not applied yet.** |
| `tested` | no | `null` or `"YYYY-MM-DD"` | A note: the date of the last real run. `scripts/run_profile.py` writes it. It does not change the profile hash. |

## 3. The token

- `default` is the **only** profile with no token: it is what a request with **no `profile`** runs. Every other profile needs `token_sha256`.
- The service never stores the token: it stores the **SHA-256**; the client sends the token; the service hashes it and compares in constant time. A wrong token, an unknown profile and a disabled profile give the **same** generic `INVALID_PROFILE` answer (the reason is only in the log).
- The files hold a **placeholder of 64 zeros** (no token has that hash, so nobody can use those profiles). Before a client can use a profile, put the real hash there. Make the token long and random, keep it in the client's secrets, never write it in a file:

```bash
python -c "import secrets,hashlib; t=secrets.token_hex(32); print('token (give it to the client):', t); print('token_sha256 (goes in the file):', hashlib.sha256(t.encode()).hexdigest())"
```

- **State (2026-11-10, development):** the six profiles with a token (`identification`, `chat`, `special`, `dynamics`, `movement`, `gesture`) hold the real SHA-256 of a random development token, each its own; the placeholder is only what a new profile starts with. The plain tokens are not in the repository: whoever generated them gave them to the web's backend. Production needs its own tokens (change the hash, redeploy).

- The token is a check against a mistake, **not access control** (Q08-8). Anyone who can reach the port and knows the token can use the profile; do not rely on it to protect customer data.
- Changing a token does **not** change `profile_hash`; changing anything else does.

## 4. Inputs

`inputs` lets a client hand a profile what an earlier profile already found (chaining: `identification`, then `chat`, then `gesture`).

- `requires`: fields the request **must** carry; a missing one is refused with `MISSING_INPUT` before any model is called.
- `accepts`: fields it **may** carry. A field in neither list is refused with `INVALID_INPUT`.
- Every name must be a field of `config/state_fields.json`. The data-flow check also uses `requires`: a step may only read a field that an input, `initial_state` or an earlier step provides (`{step} reads {field} but no step before it writes it...`).
- **What a client can really send** is narrower than the catalog: the structured fields `intent`, `user_goal`, `mcp_routing`, `task_category`, `actions`, `missing_information`, `constraints`, `safety_and_validation`, `next_step` (read with the same code and checks as a model answer) and the plain values `reply` (text) and `speech_seconds` (number). Listing any other catalog field (for example `movements`) passes the check but every request that sends it gets `INVALID_INPUT`. The model's token usage and raw text are always dropped.
- Inputs are **data, never instructions**: they fill state fields; they are not added to a prompt as text of the client.
- A profile with no `inputs` accepts none.

## 5. Tools

`tools` is an object with two optional lists:

| Key | Values |
|---|---|
| `servers` | names of servers in `mcps/`: every tool of that server |
| `tools` | `"server.tool"`, or a bare tool name when only one server has it |

- **No `tools` key at all** (or `null`): no limit, every available server. Only `special` does this today.
- **Any object, including `{}` and `{"servers": []}`: only what it names**, so those two mean *no tool at all*.
- The same object can be written at five levels: the profile (`tools`), `flows.<flow>.tools`, the flow file's `tools`, a step's `tools` inside the flow file, and `overrides.<step>.tools`. A step may use **only what every level that is set allows** (an intersection). A lower level can narrow, never widen.
- Names are checked against `mcps/` by `scripts/check_agent.py`: unknown server, unknown tool, a bare name that two servers own, and a `server.tool` of a server with no `allowed_tools` are errors.

## 6. Models, per-flow and per-step changes

**Model order (most specific wins; the whole list is replaced, not merged):**

1. `flows.<flow>.steps.<step>.models`
2. `overrides.<step>.models`
3. `flows.<flow>.models`
4. `models`
5. the step's `default_models` (in `step_defs/`)

A value is a set name (`"claude_mixed"`; the set's entry for the step, else its `default`) or a list of ids (`["claude-haiku-4-5", "gemini-3.1-flash-lite"]`: the first answers, the rest are the fallback after a lack of capacity). Only steps that have a model are valid names (`motion_validator`, `gesture_builder` and `action_executor` are code). Details and the id list: [model_sets/README.md](../model_sets/README.md).

**`overrides.<step>`** accepts only `models`, `tools`, `prompt_replace`, `prompt_append`:

```json
"overrides": {
  "draft_writer": {
    "models": ["claude-sonnet-5-5"],
    "prompt_append": {"text": "Always answer in Catalan."},
    "tools": {"servers": []}
  }
}
```

- `prompt_replace` / `prompt_append` take **exactly one** of `{"file": "prompts/..."}` or `{"text": "..."}`, non-empty. A file must be **inside `prompts/`** (recommended: `prompts/profiles/<profile>/<step>.txt`; nothing may use `..`).
- Replace is applied first, then append (`replace` or the step's own prompt, then a blank line, then the append). The generic rules, the capabilities and the date always stay **in front**, and the **answer schema is the step's**: a profile can never change the format of an answer.
- The step must have a prompt (an LLM step) and must be a step of the profile's flow (a per-action step such as `cognitive_worker` counts when the flow has `action_executor`). `user_clarification` and code steps cannot be changed.
- An override changes `profile_hash`.

**`flows.<flow>`** accepts only `models`, `tools` and `steps`. `steps.<step>` accepts `models`.

## 7. Limits to know

- **Every request runs exactly one profile.** The service does not route or chain: the client calls `identification`, reads `data.task_category.domain`, calls the profile that answers, then `gesture`. Asking `identification` and then `special` runs the triage twice and nothing warns about it.
- A run that asked the user a question is resumed by the **next message of the same profile** (`PROFILE_MISMATCH` otherwise). Only a flow with `on_pause`/`on_resume` can ask.
- A profile that can plan and call tools (`special`, `dynamics`, `default`) is bounded by `AI_AGENT_MAX_ATTEMPTS`, `AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE` (5) and the 60 s tool wait of one message.
- Data in the answer or in `inputs` reaches the model providers you name in `models` (and Langfuse when keys are set). A profile with `dynamics` tools reaches customer data of Business Central; personal columns are masked first.
- The data-flow check and the model/schema checks run at start and in `check_agent.py`; **tool behaviour, answers and costs are only known after a real run** (`python scripts/run_profile.py <profile>`, it asks first and costs money; `--mock` is free).

## 8. Make a new profile (checklist)

1. Copy the closest profile, rename the file **and** `name`, write `about`.
2. Choose `flow`; choose `models` (a set or a list); decide `tools` (do not leave it out unless every server is acceptable).
3. If a client will chain it, write `inputs.requires` / `accepts` (section 4).
4. Put a real `token_sha256` (section 3). Leave `tested` as `null`.
5. `python scripts/check_agent.py`, then `python scripts/check_agent.py --explain <name>` (steps, model per step and where it comes from, tools, prompts, hash, cost of a full plan).
6. `python scripts/run_profile.py <name> --mock`, then the real run when you accept the cost; the date goes to `tested`.
7. Update `docs/models/profiles.md` (`python scripts/model_tables.py --profiles`; generated, not by hand), the table below and `docs/architecture/architecture.md` / `README.md` if the list of profiles changed.

## 9. The profiles here

| Profile | Flow | Models | Tools | Token | Inputs |
|---|---|---|---|---|---|
| `identification` | `identification`: the triage alone; `default_return: full` | `proven` | none | yes | none |
| `chat` | `conversation`: draft writer, editor | `claude_haiku` | none | yes | requires `user_goal`, `task_category`; accepts `intent`, `constraints`, `missing_information`, `next_step` |
| `special` | `special`: triage, plan, check, execute, write, edit | `claude_mixed` | no limit (every configured server) | yes | none |
| `dynamics` | `special` | `claude_mixed` | only `dynamics_microservice` | yes | none |
| `default` | `special` (what a request with no profile gets) | `proven` | none | **no** | none |
| `movement` | `movement`: motion planner, motion validator | `proven` | none | yes | accepts `intent`, `user_goal`, `task_category`, `constraints`, `missing_information`, `next_step` |
| `gesture` | `expression`: emotion reader, gesture builder | `proven` | none | yes | requires `reply`; accepts `speech_seconds` |

`token_sha256` of the shipped profiles is still the placeholder of zeros (nothing can use them until it is replaced).
