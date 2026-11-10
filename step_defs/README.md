# step_defs/

One JSON **declaration** per step: what a step is, which prompt it uses, what it reads from and writes to the state, and the shape of the answer the model must give (PR-005 section 3.2; ADR-015). Named `step_defs` so it does not share a name with `application/steps/`, which holds the Python of the **code** steps. A flow ([flows/README.md](../flows/README.md)) lists steps by the name of the file here.

**Adding an LLM step = one JSON file here + one prompt file in `prompts/`** (no Python), as long as its input and result fit what is described below. A step that needs real code (a new calculation, a new way to build the input) needs a Python function; see section 7.

Read at start by `application/steps/declared.py` and checked by `application/engine/assemble.py`; `python scripts/check_agent.py` checks every file (it reads files only: no model is called).

## 1. File rules

- File name = step name = `name` inside. **Always write `name`**: the engine reads it. A mismatch refuses the file.
- `schema_version` must be `1`. An unknown key is an error. Keys that start with `_` are ignored; a file that starts with `_` is not loaded.
- A step with a problem makes **every flow that uses it unusable**, and so every profile on those flows.
- Changing a declaration changes how every profile behaves; run the tests and read the golden-file diff on purpose.

## 2. The three kinds

| `kind` | Calls a model? | Runs | Needs |
|---|---|---|---|
| `llm` | yes, once | a step of a flow | prompt, answer (pieces or schema), default model, intent, format name, `legacy_id`, `group` |
| `llm_per_action` | yes, once per planned action | **only inside `action_executor`**, never listed in a flow | the same, plus `for_each: "actions"` and `answer.schema_file` |
| `code` | no | a step of a flow | `function`, the name of an existing Python step; **no prompt, no model** |

Today the `llm_per_action` steps are exactly `cognitive_worker` (an action that needs no tool), `mcp_operator` (a tool call) and `data_engineer` (cleans a tool result); the code of `action_executor` decides which one runs for each action. A **new** per-action step needs Python in `action_executor` to be called: a declaration alone does not make it run.

## 3. All fields

| Key | Applies to | Required | Values | Meaning |
|---|---|---|---|---|
| `schema_version` | all | yes | `1` | |
| `name` | all | yes | = file name | The step name used by flows, model sets, profiles' `overrides`, metrics and `check_agent.py`. |
| `about` | all | no | text | Documentation only. |
| `kind` | all | yes | `llm`, `llm_per_action`, `code` | Section 2. |
| `legacy_id` | llm kinds | yes | whole number, **unique** across all steps | The old phase number, a **label** for failures, metrics and ordering. Pick one that no other step uses (shipped: 1-8, 20, 21, 30, 31, 40; 9 and 99 belong to the answer checker and the clarification). |
| `group` | llm kinds | yes | `identification`, `common`, `special`, `movement`, `expression` | The family it sorts with (labels, ordering of tables). Not a permission. |
| `prompt` | llm kinds | yes | `{"file": "prompts/<id>_<name>.txt"}` | The step's prompt. **Only `file` is supported** (an inline text is refused). The file must exist inside the project. The generic rules (`prompts/0_generic_prompt.txt`), `capabilities.txt` and the date are put in front by the engine. |
| `default_models` | llm kinds | yes | list of model ids; **the first must be a Google model** | What the step uses when no model set or profile says anything (section 5). |
| `intent` | llm kinds | yes | `{"primary": text, "secondary": [text], "confidence": number}` | The intent label sent with the call. No other key is allowed. Copy it from a similar step. |
| `format_name` | llm kinds | yes | non-empty text | The name of the answer format sent to the model (convention: `<step>_phase<id>_response_format`). |
| `answer` | llm kinds | yes | see section 4 | The shape of the answer. |
| `reads` | all | see rule | list of state fields | What the model is told (section 6). Required unless `functions.input` is given. |
| `writes` | all | recommended | list of state fields | Where the answer goes. The check for a step with no `reads`/`writes` lists is skipped, so always write both. |
| `write_always` | llm | no | `true` / `false` | `false` (default): a field is written only if the answer's value is not empty. `true`: it is written even when empty (used by the planner and the gate, so an empty plan replaces an old one). |
| `for_each` | `llm_per_action` | yes | `"actions"` | Run once per action. |
| `function` | `code` | yes | name of a Python code step | Which code runs (`action_executor`, `motion_validator`, `gesture_builder`). Must exist in `application/steps/` as a code step. |
| `functions` | llm kinds | no | `{"input": name, "apply": name, "extra": name}` | Named Python functions of `application/steps/functions.py`, for when plain `reads`/`writes` are not enough (section 7). Unknown slot or name is an error. |
| `tools` | all | no | `{"servers": [...], "tools": [...]}` | **Checked against `mcps/` but not applied**: the scope of a step is built from the profile, the flow file and `overrides.<step>.tools`, not from this key. Put limits there instead. |
| `data` | all | no | `{"reads": [text]}` | **Reserved** for a future data policy (Q07-16). Only its shape is checked; nothing reads it. Do not rely on it. |

## 4. `answer`: what the model must return

Exactly one of three forms (llm kind `llm`):

1. **`pieces`** (the usual way): build the answer from existing pieces of `schema/response/`.

```json
"answer": {
  "required": ["user_goal", "next_step"],
  "pieces": [
    {"name": "user_goal", "file": "general/user_goal/user_goal.schema.json", "key": "user_goal"},
    {"name": "next_step", "file": "general/next_steps/next_step.schema.json", "key": "next_step"}
  ]
}
```

   - `name`: the property name in the model's answer; `file`: a file under `schema/response/` (path relative to it); `key`: the property inside that file (default: `name`; the file must contain it).
   - `required`: names of pieces only; every name must be in `pieces`. `pieces` must not be empty.
   - `mcp_servers: true` on a piece makes it the **actions** piece: the `server_id` allowed values become the MCP servers the step may use in that run (this is how the planner can only name allowed servers).
2. **`schema`**: a whole JSON Schema object written inline (`required`, `properties`).
3. **`schema_file`**: the path of a whole schema under `schema/response/`.

For `llm_per_action` steps, `answer.schema_file` must be the **actions schema file** (`general/actions/actions.schema.json`), and `for_each` must be `"actions"`.

Pieces you can reuse (folders of `schema/response/`): `general/intent`, `user_goal`, `mcp_routing`, `task_category` (`.type`, `.domain`, `.complexity` ...), `actions`, `missing_information`, `constraints`, `safety_and_validation`, `next_steps`; `motion/` (`is_motion_request`, `movements`, `spoken_reply`) and `expression/` (`emotion`, `intensity`, `improvised`). **A new piece is not a file here**: `schema/response/general/full.schema.json` (or the motion/expression one) is the only file edited by hand; then `python scripts/split_schemas.py --write` rebuilds the others, and `domain/`, the prompt and the golden file must be kept in sync (`docs/rules/schemas-and-prompts.md`).

Limits: with Claude models the answer schema may nest at most **3 levels**; a custom `schema`/`schema_file` is checked for it for every Claude model a profile puts on the step (`unsupported ... cannot run`).

## 5. Default models

`default_models` is the **last level** of the model order (profile `flows.<flow>.steps.<step>.models` > `overrides.<step>.models` > `flows.<flow>.models` > `models` > this). Its first model must be a Google model of the code catalog (the check says so), because it also defines the step's cost row. A profile or a model set normally overrides it. See [model_sets/README.md](../model_sets/README.md).

## 6. `reads` and `writes`

Both are lists of fields of **`config/state_fields.json`** (the closed catalog; a field that is not in it is an error, with the list). A non-programmer cannot add a field: that needs the state class and `domain/`.

Fields every run has from the start (`always`): `message`, `history`, `answers`. Others the flows fill: `intent`, `user_goal`, `mcp_routing`, `task_category`, `actions`, `missing_information`, `constraints`, `safety_and_validation`, `next_step`; motion state only: `motion_requested`, `movements`, `motion_rejection`, `spoken_reply`, `speak_movements`; expression state only: `reply`, `speech_seconds`, `emotion`, `intensity`, `improvised` (`movements` is in both). The fields of the motion and expression families exist only in the state of a flow that contains `motion_planner` or `emotion_reader` (section 5 of [flows/README.md](../flows/README.md)); reading one in another flow fails at run time, not in the check.

`reads` entries:

| Written | Meaning |
|---|---|
| `"user_goal"` | the field, told to the model under the same name |
| `"actions?"` | the field **may be missing**: no earlier step has to write it |
| `{"user_message": "message"}` | the model is told the field `message` under the name `user_message` (rename only) |

`writes` entries are plain field names (`"field?"` is also accepted).

The **data-flow check** uses them: in every profile's flow, each step may only read what the fields-always, the profile's `inputs.requires`, `initial_state` or an earlier step provide; the result step must write `user_goal`. A wrong order or a missing writer is an error naming both ends.

With plain `writes`, each field is read from the parsed answer under the **same name** and copied into the state. A `writes` name the answer does not carry is not caught by the check; only a mock or real run shows it.

## 7. `functions`: when a list is not enough

A declaration cannot contain code. When what the model is told, or how its answer is stored, is more than a list of fields, it **points to a function that a developer wrote** in `application/steps/functions.py`. The names today:

| Slot | Names | Used by |
|---|---|---|
| `input` (builds what the model is told) | `message_with_history`, `planner_input`, `safety_input`, `exchange_text` | `triage_specialist`, `motion_planner` (the first); `project_manager`; `safety_quality_gatekeeper`; `emotion_reader` |
| `apply` (stores the answer) | `load_from_response`, `motion_plan_result`, `emotion_result` | `triage_specialist`; `motion_planner`; `emotion_reader` |
| `extra` (what a per-action step is told besides the action) | `worker_extra`, `operator_extra` | `cognitive_worker`; `mcp_operator` |

Any other name is refused. A **new** function is a code change (and a test) in `application/steps/functions.py`. Do not copy a name onto a step it was not written for: `planner_input`, for example, adds the available MCP servers.

## 8. Make a new LLM step (checklist)

1. Write the prompt in `prompts/<id>_<name>.txt` (see `docs/rules/schemas-and-prompts.md`; the golden file changes on purpose).
2. Copy the closest declaration; set `name`, `about`, a **unique `legacy_id`**, `group`, `prompt.file`, `default_models`, `intent`, `format_name`.
3. Choose the answer pieces (section 4) and `reads` / `writes` (section 6). Add `write_always` only if an empty value must replace an old one.
4. Add the step to a flow (a `step` entry), put it where its `reads` are available, and consider `pause_if` / `retry_on_status` there.
5. Optional: give it a model in a model set (the name becomes a valid key by itself) or a profile `overrides`.
6. `python scripts/check_agent.py`, then `python -m pytest tests` (`tests/test_step_declarations.py`, `tests/test_phase_structure.py`, golden file), then `python scripts/run_profile.py <profile> --mock`.
7. Update `docs/architecture/architecture.md`, `docs/rules/schemas-and-prompts.md`, `README.md` (layout), and `docs/models/*` (`python scripts/model_tables.py --write`; generated, do not edit).

A `code` step additionally needs `application/steps/<group>/<name>.py` with the constants at its top (`PHASE_ID`, `STEP_NAME`, `LLM = False`) and `register_step(__name__, "code")`, plus its declaration here.

## 9. Limits to know

- Only the **first** model of `default_models` is used as the default; the rest of that list is not a fallback chain (fallbacks belong in a model set or profile).
- One declaration = one prompt file; a profile can append to or replace it (`overrides.<step>.prompt_append` / `prompt_replace`), never the schema.
- No branching, no loops, no tool calls of its own: tools are used only through the per-action `mcp_operator` and the planner, limited by the scope of the profile/flow/step.
- `data` and `tools` of a declaration have no effect at run time; nothing here sets the MCP servers of a profile.
- Every LLM call is one record in the metrics; a per-action step makes one per action (the cost grows with the plan, `AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE` limits the tool ones).

## 10. The steps here

| Step | Kind | Group | `legacy_id` | Default model | Reads | Writes |
|---|---|---|---|---|---|---|
| `triage_specialist` | llm | identification | 1 | gemini-3.1-flash-lite | `message`, `history`, `answers` | the whole classification |
| `project_manager` | llm | special | 2 | gemini-3.6-flash | `user_goal`, `task_category`, `history`, `answers` | `actions`, `next_step` |
| `safety_quality_gatekeeper` | llm | special | 3 | gemini-3.6-flash | `actions`, `next_step`, `answers` | `safety_and_validation`, `next_step` |
| `cognitive_worker` | llm_per_action | special | 4 | gemini-3.6-flash | `user_goal`, `actions` | `actions` |
| `mcp_operator` | llm_per_action | special | 5 | gemini-3.6-flash | `safety_and_validation`, `actions` | `actions` |
| `data_engineer` | llm_per_action | special | 6 | gemini-3.1-flash-lite | `actions` | `actions` |
| `draft_writer` | llm | common | 7 | gemini-3.6-flash | `message` (as `user_message`), `user_goal`, `task_category`, `actions?`, `constraints?` | `user_goal` |
| `editor_in_chief` | llm | common | 8 | gemini-3.6-flash | `user_goal`, `constraints?`, `next_step?` | `user_goal`, `next_step` |
| `motion_planner` | llm | movement | 20 | gemini-3.6-flash | `message`, `history`, `answers` | `motion_requested`, `movements`, `spoken_reply`, `next_step` |
| `motion_validator` | code | movement | 21 | none | `motion_requested`, `movements` | `movements`, `motion_rejection` |
| `emotion_reader` | llm | expression | 30 | gemini-3.1-flash-lite | `message`, `reply` | `emotion`, `intensity`, `improvised` |
| `gesture_builder` | code | expression | 31 | none | `emotion`, `intensity`, `improvised`, `speech_seconds?` | `movements` |
| `action_executor` | code | special | 40 | none | `actions`, `user_goal`, `safety_and_validation`, `answers` | `actions` |

The two prompts the engine runs itself (`answer_checker`, phase 9, and `user_clarification`, phase 99) are **not** declared here: they are Python (`application/steps/common/`), run through the flow's `on_pause` / `on_resume` hooks, and they can be given a model in a model set or profile but their prompt cannot be overridden by a profile.
