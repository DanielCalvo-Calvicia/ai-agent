# flows/

One JSON file per **flow**: an ordered list of steps with named pause and retry rules (PR-005 section 3.3; ADR-015). A profile names one flow (`"flow": "special"`). A flow says **what runs and in what order**; it does not say which models (profile), which tools at the profile level (profile), or what a step does (`step_defs/`). **No branches and no sub-flows**: the steps run top to bottom.

Read at start by `infrastructure/outbound/config/file_source.py`, checked by `application/engine/assemble.py` and built into a `Flow` by `application/engine/flow_file.py`. `python scripts/check_agent.py` checks every file.

## 1. File rules

- File name = flow name = `name` inside. A mismatch refuses the file. The flow names are also the `flow` field of an answer and a key of the metrics: **renaming a flow changes both**.
- `schema_version` must be `1`. An unknown key is an error. Keys that start with `_` are ignored; a file or folder that starts with `_` is not loaded.
- The five shipped names (`identification`, `conversation`, `special`, `movement`, `expression`) are the names the old Python flows had.

## 2. All fields

| Key | Required | Values | Meaning |
|---|---|---|---|
| `schema_version` | yes | `1` | Format version. |
| `name` | yes (always write it) | text, equal to the file name | Public name of the flow. |
| `about` | no | text | Documentation only. |
| `steps` | yes | non-empty list | The steps in order. Each entry is a **step name** or an **object** (section 3). |
| `on_pause` | see rule | `"user_clarification"` | What the engine does when a step asks the user: turn the missing data into one question. |
| `on_resume` | see rule | `"answer_checker"` | What the engine does with the next message of the user: decide whether it answers the question, confirms, declines, or stops. |
| `result_from` | yes | the name of **a step in this flow** | The step whose result is the flow's result. It also decides *what kind* of result (section 5). |
| `tools` | no | `{"servers": [...], "tools": [...]}` | Tool limit for the whole flow (same format and intersection rule as in [profiles/README.md](../profiles/README.md) section 5). |
| `models` | no | a model set name or a list of ids | **Checked but not applied**: models are chosen by the profile (`flows.<flow>.models` in the profile). Do not rely on it. |

**Rule for `on_pause` / `on_resume`:** a flow with at least one `pause_if` step **must** have `on_pause`, and one that can be resumed must have `on_resume`. The check does not catch the omission: the failure is raised **at run time** (`step X can ask the user, but the flow has no on_pause hook` / `has no on_resume hook`). A flow with no step that can ask carries neither (as `conversation` and `expression`).

## 3. A step entry

A plain name (`"draft_writer"`) is a step with no rules. An object has these keys, all but `step` optional:

| Key | Values | Meaning |
|---|---|---|
| `step` | a name from `step_defs/` or a Python code step | Required in an object. The names available are in section 6. |
| `pause_if` | `"needs_user_input"` | After the step, if the condition is true the flow **stops and asks the user** instead of going on. The condition is true when the step's `next_step.status` is `awaiting_user_input` (a detail is missing) or `awaiting_confirmation` (a yes/no is needed; a yes resumes **after** the step, the answer checker decides). The next message of the same profile resumes **at the same step**, now with the answer. |
| `retry_on_status` | `true` / `false` (default `false`) | Run the step again while its answer says `retry` or `error` in `next_step.status`, up to `AI_AGENT_MAX_ATTEMPTS` (3, first try included). After that the request fails (`reported_error`). |
| `tools` | `{"servers": [...], "tools": [...]}` | Tool limit for **this step only**. Can only narrow the profile's and the flow's limit. |
| `optional` | any | Accepted by the check, **ignored** by the engine. Do not use it. |

## 4. Names a flow may use: they are written in Python

A flow cannot invent a step, a condition or a hook; it can only **combine** the ones that exist. A developer adds a new one in code.

| What | Allowed values today | Where they live |
|---|---|---|
| step | the names in section 6 | `step_defs/*.json` (LLM steps) and `application/steps/**` (code steps) |
| `pause_if` | `needs_user_input` | `application/steps/conditions.py` |
| `on_pause` | `user_clarification` | `application/steps/hooks.py` |
| `on_resume` | `answer_checker` | `application/steps/hooks.py` |

A wrong name is reported with the list of valid ones (`unknown condition 'x'. Conditions: needs_user_input`).

## 5. What `result_from` decides

The step named in `result_from` also picks how the answer is built (`application/steps/hooks.py`, `RESULT_BUILDERS`):

| `result_from` | The flow returns |
|---|---|
| `triage_specialist` | no text (classification only; the client reads the state, `default_return: full` on the profile) |
| `motion_validator` | the spoken line and the arm movements (`directives`) |
| `gesture_builder` | the gesture: movements only, no reply of its own |
| any other step | the final text the writer/editor left (`user_goal`'s text) |

If the result step is an LLM step it must write `user_goal` (the session keeps the input and output of the request in it), or the check fails.

The **state a flow starts with** depends on its steps: a flow that contains `motion_planner` starts a motion state, one that contains `emotion_reader` an expression state, any other the general state. Do not mix steps of those families in one flow.

## 6. Steps available to put in a flow

| Step | Kind | Used in | Note |
|---|---|---|---|
| `triage_specialist` | LLM | `identification`, `special` | Classifies; can ask. |
| `project_manager` | LLM | `special` | Plans the actions; can ask; sees only the tools its scope allows. |
| `safety_quality_gatekeeper` | LLM | `special` | Safety check; can ask. |
| `action_executor` | code | `special` | Runs the planned actions, one model call each, using `cognitive_worker`, `mcp_operator` and `data_engineer` itself. |
| `draft_writer` | LLM | `conversation`, `special` | First text. |
| `editor_in_chief` | LLM | `conversation`, `special` | Final text. Normally last, with `retry_on_status`. |
| `motion_planner` | LLM | `movement` | Can ask. |
| `motion_validator` | code | `movement` | Checks the movements against fixed limits. |
| `emotion_reader` | LLM | `expression` | One cheap call. |
| `gesture_builder` | code | `expression` | Builds the random arm gesture. |

**Not allowed in a flow:** `cognitive_worker`, `mcp_operator` and `data_engineer` (they run once per action inside `action_executor`; listing them is **not** caught by `check_agent.py` and fails when the flow is built, at run time) and `answer_checker` / `user_clarification` (engine hooks, not steps).

## 7. Order and data flow (what the check enforces)

- Every step reads **only what is available**: the fields every run has (`message`, `history`, `answers`), fields the profile's `inputs.requires` or `initial_state` give, and fields an **earlier** step writes (`step_defs/*.json` `reads` and `writes`). A step that reads something nobody provides is an error naming both. A read written `"field?"` may be missing.
- So the **order matters**: `draft_writer` needs `user_goal` and `task_category`, which `triage_specialist` writes, or a profile `requires` them (that is how `chat` skips the triage).
- A step that is missing its declaration (or is unknown) is an error. A step whose declaration has a problem makes every flow that uses it unusable.
- `result_from` must name a step **in** `steps`.

## 8. Limits to know

- Linear only: no loop, no jump, no condition other than `pause_if`; the only repetition is `retry_on_status` on one step.
- Only a step whose answer carries `next_step` can ask or retry (`status` is one of `proceed`, `awaiting_user_input`, `awaiting_confirmation`, `retry`, `error`, `complete`); `pause_if` or `retry_on_status` on a step that never writes `next_step` does nothing.
- A step that can ask makes the profile **resumable**: sessions keep the paused run in memory only (lost on restart).
- The tools of a step are the **intersection** of every level (profile, `flows.<flow>.tools` of the profile, this file's `tools`, the step's `tools`, `overrides.<step>.tools`).
- Changing a flow changes the `profile_hash` of every profile that uses it.

## 9. Make a new flow (checklist)

1. Copy the closest file, rename it **and** `name`, write `about`.
2. List the steps, add `pause_if` / `retry_on_status` where the step can ask or report a retry, set `result_from`, add the two hooks if anything can ask.
3. Check the order against section 7; if a step needs a field nobody writes, add it as a profile `inputs.requires`.
4. Write a profile that names it (`"flow": "<name>"`) and run `python scripts/check_agent.py` and `--explain <profile>`.
5. Update `docs/architecture/architecture.md` (flows) and `README.md` if the list changed. The `flow` field of an answer and the metrics will carry the new name.

## 10. The flows here

| Flow | Steps | Asks the user? | Used by |
|---|---|---|---|
| `identification` | `triage_specialist` | yes | `identification` |
| `conversation` | `draft_writer`, `editor_in_chief` | no | `chat` |
| `special` | `triage_specialist`, `project_manager`, `safety_quality_gatekeeper`, `action_executor`, `draft_writer`, `editor_in_chief` | yes (first three) | `special`, `dynamics`, `default` |
| `movement` | `motion_planner`, `motion_validator` | yes | `movement` |
| `expression` | `emotion_reader`, `gesture_builder` | no | `gesture` |
