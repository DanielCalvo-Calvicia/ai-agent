# Schemas and prompts

What the LLM is told (prompts) and what it must answer (JSON Schemas), and how they stay in sync with the code.
**Prompts, schemas and `domain/` must change together**: a field edited in one and not in the others breaks a flow
silently, because the model follows the prompt and the schema, and the mapper reads only what it knows.

## 1. Prompts (`prompts/`)

Flat folder, one file per phase: `<id>_<name>.txt`. Which phase uses which file is the `PROMPT_FILE` constant of the phase
file, never a table somewhere else.

| File | Phase / use |
|---|---|
| `0_generic_prompt.txt` | the rules of every phase (machine-to-machine, exactly one JSON object, follow the schema, `next_step` is the control flow) |
| `capabilities.txt` | what the robot can and cannot do (arms: yes; files, email, the internet, walking, seeing: no). Every phase gets it, so edit it to change what the agent believes it can do |
| `1_triage_specialist.txt` | triage: classification, **and the meaning of each `task_category.domain` value, which decides the flow** |
| `2_project_manager.txt` | the plan (never plans a movement) |
| `3_safety_quality_gatekeeper.txt` | the safety gate |
| `4_cognitive_worker.txt`, `5_mcp_operator.txt`, `6_data_engineer.txt` | the per-action phases |
| `7_drawf_writter.txt` (sic) | the draft writer |
| `8_editor_in_chief.txt` | the editor |
| `9_answer_checker.txt` | the answer checker |
| `20_motion_planner.txt` | the motion planner (movements and `spoken_reply`) |

The system message of a phase is `0_generic_prompt` + `capabilities` + the current date and time + the phase prompt
(`application/system_prompts/general.py`). Phase 99 (the question for the user) has its prompt inside its phase file.

**Input format:** phase 1 receives the user text (with "Conversation so far:" and "Information the user gave when asked:"
sections when there are earlier turns or answers). Every other phase receives `str()` of a Python dict whose values are
domain objects shown as their `repr`. The prompts describe those inputs by the dict keys. Changing a dict key or a
domain class name changes what the model sees: that is why the golden test records every message.

## 2. The response schemas (`schema/response/`)

Two trees, each generated from one file:

| Tree | Source file | What it describes |
|---|---|---|
| `general/` | `general/full.schema.json` | the structured answer of the text flows: `intent`, `user_goal`, `task_category`, `actions`, `missing_information`, `constraints`, `safety_and_validation`, `next_step`, `mcp_routing` |
| `motion/` | `motion/full.schema.json` | the movement flow's own fields: `is_motion_request`, `movements` (`arm`, `degrees`, `direction`), `spoken_reply`. Its `next_step` is the general one |

**`full.schema.json` is the only file you edit.** Every other file is generated:

```powershell
& windows\Scripts\python.exe scripts\split_schemas.py            # check: lists what differs from the full schema
& windows\Scripts\python.exe scripts\split_schemas.py --write    # write the tree, remove files that are not in it
```

`tests/test_schema_tree.py` fails when a node has no file, a file has no node, or the tree drifted from the full schema.

### 2.1 The layout of a tree

Every property, at any depth, has a file `{ "<last key>": <schema> }` named by its dotted path.

- a node **with children** (an object, or an array of objects) gets a **folder** named after it, holding its own file (the
  whole subtree, which is what the phases load), one file per child, and for an array its `<path>.item.schema.json`;
- a node **without children** (string, number, boolean, free-form object, a `$ref`) is one file in its parent's folder;
- the actions file is the exception: a bare array schema with its `$defs`, because an action can contain `subactions` of
  the same shape (a `$ref`), and the pipeline loads it that way;
- the folder of `next_step` is `next_steps/` (kept: phases point at it).

```text
schema/response/general/
  full.schema.json
  intent/intent.schema.json, intent.primary.schema.json, intent.secondary.schema.json, intent.confidence.schema.json
  actions/actions.schema.json, actions.item.schema.json, actions.id..., actions.subactions.schema.json
  actions/mcp_context/actions.mcp_context.schema.json, ...server_id..., ...tool_name..., ...parameters...
  next_steps/next_step.schema.json, next_step.status.schema.json, ...
  ...
schema/response/motion/
  full.schema.json, is_motion_request.schema.json, spoken_reply.schema.json
  movements/movements.schema.json, movements.item.schema.json, movements.arm..., movements.degrees..., movements.direction...
```

## 3. How a phase gets its schema

A phase file lists the pieces it needs as `SCHEMAS = {name: SchemaRef(file, key)}`. `PhaseRunner` loads them
(`support/schemas.py`, cached, independent of the working directory) and builds the response format with
`object_schema(required, properties)`. For the actions, `actions_schema(mcp_server_names)` fills `mcp_context.server_id`
with `""` or the names of the MCP servers of that request. Domain, motion and general pieces mix freely: the motion
planner takes `is_motion_request`, `movements` and `spoken_reply` from `motion/` and `next_step` from `general/`.

The `domain` enum of triage is the routing key: `software`, `data`, `writing`, `design`, `research`, `operations`,
`communication`, `system`, `movement`. `communication` and `movement` have their own flows; the rest go to the special flow.
The arms (`left`, `right`) and directions (`forward`, `reverse`) of the motion schema are written out in the schema and
checked against `ARMS` and `DIRECTIONS` by `test_schema_tree.py`.

## 4. Changing an answer, step by step

1. Edit `schema/response/<tree>/full.schema.json`, then run `scripts/split_schemas.py --write`.
2. Edit the prompt that tells the model about the field.
3. Edit the domain object (`domain/value_objects/llm_response/<section>/`) and the mapper
   (`infrastructure/outbound/llm/response_mapper.py`, one function per section) so the value is read.
4. If a phase must use the new piece, add it to that phase's `SCHEMAS` (and `REQUIRED`) and to its `apply`.
5. Run the tests. The golden test will fail because the schema or prompt changed: read the diff, and regenerate it on
   purpose with `UPDATE_GOLDEN=1 python -m pytest tests/test_flow_golden.py`.

## 5. Known gaps

- `constraints`, `mcp_routing` and `missing_information` have schemas, domain objects and mapper functions, but no phase asks
  for them today.
- `next_step.retry_action_id` is read and kept, but nothing acts on it.
- `Payload` imports `Intent` from `llm_response`: a request carries the intent of its call.
