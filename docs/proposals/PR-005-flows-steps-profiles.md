# Profiles, flows and steps as three separate, pluggable layers

Status: **ACCEPTED 2026-11-02** by the maintainer after review (two corrections made in the review: the triage in `special` and `dynamics`, section 3.3, and no error for a second triage). Not built: it is planned in epics [T-05](../tasks/T-05_profiles-flows-steps/T-05_profiles-flows-steps.md) and [T-06](../tasks/T-06_redesign/T-06_redesign.md); [ADR-015](../decisions/ADR-015-profiles-flows-steps.md) records the decision. Section 12 lists the assumptions the owner did not answer. Written after the answers of [Q05](../setup/questionnaires/Q05_flows-steps-profiles.md) to [Q09](../setup/questionnaires/Q09_profiles-per-message.md); each decision below names the answer it comes from (`Q07-6` = question 6 of Q07).
History: the first draft of 2026-10-30 assumed one active profile, models only and a router inside the service. The answers changed all three; this text replaces it.

Vocabulary (owner, Q06-5): **profile** (also called *agent*) is what a client asks for; **flow** (also *workflow*) is an ordered list of steps; **step** is one job. The word *phase* and the numeric ids stay only as labels (Q07-9).

## 1. Goal

1. **Separation.** A step knows how to do one job. A flow knows the order of steps. A profile knows which flow (or list of steps), which models, which tools and which prompts one client gets. Each lives in its own file and names the others only by name.
2. **A profile is a complete recipe**, chosen by the client on every request, so one service serves the robot, a web chat and other projects with different behaviour (Q05-1, Q06-16).
3. **Plug and play.** A new step, flow or profile is added by writing files, not by editing the engine, a router or a catalog; a mistake fails at start with a clear message (Q05-3, Q05-5).
4. **A clear separation of the sources.** Where the files come from (today the repository, later SQL, S3, LangChain services) must not matter to the rest (Q06-30, Q07-17).

## 2. What changes for the client (read this first)

The robot's Brain used to make **one call per utterance** and the service decided inside which flow answered (ADR-003, ADR-004). In the new design **the client decides**: it asks a profile, reads its result and asks the next profile. The service no longer routes (Q08-1, Q09-7).

```text
Brain ──"hola"──> profile identification ──> output: Response (intent, user_goal, task_category, ...)
Brain ──"hola" + inputs=<that Response>──> profile chat ──> response: "¡Hola! ¿En qué puedo ayudarte?"
Brain ──inputs={reply, user message}──> profile gesture ──> directives: [arm movements]
```

A client that knows what it wants calls one profile directly (a web chat asks `chat`; a test asks `special`). A client that sends no profile gets `default` (Q07-14 B).

**This is a breaking change for Brain**: until Brain chains the profiles the robot gets no movement and no gesture (the profile `default` has neither). Nothing is in production (Q05-22), so it is accepted; the change is listed in `docs/api/api.md` and the contract change is the owner's, later (Q06-16).

## 3. The model

```text
Profile  ->  Flow  ->  Step  ->  Model catalog
(a recipe)  (an order)  (a job)   (ids, prices, capabilities)
```

A layer names only the layer to its right, never the one to its left. A step never mentions a flow or a profile; a flow never mentions a profile or a model id.

| Layer | Is | Written as | Lives in (target, section 8) |
|---|---|---|---|
| **Profile** | the configuration a client asks for: **one flow, or one ordered list of steps** (Q06-1), the models, the tools, the prompts, the inputs it accepts | JSON | `profiles/<name>.json` |
| **Flow** | an ordered list of steps with named pause and retry rules; **no branches, no sub-flows** (Q06-2, Q08-1) | JSON | `flows/<name>.json` |
| **Step** | one job: `llm`, `llm_per_action` or `code` | JSON declaration + a prompt + (for `code`) a named Python function | `step_defs/<name>.json`, `prompts/`, `application/steps/` |
| **Model set** | a named table of models (the ten profiles of `step_models.json` today) usable at any level | JSON | `model_sets/<name>.json` |
| **Catalog** | the models that exist: id, provider, price | as today | `domain/.../model_catalog.py`, `config/*_models.json` |

A profile with **one step** is allowed and expected (`identification` runs only the triage). The client never asks for a step by name inside a profile (Q09-1).

### 3.1 The state is a closed catalog

A JSON step may read and write only **fields that already exist** in the domain (`user_goal`, `task_category`, `intent`, `constraints`, `actions`, `next_step`, ...; and, for the motion and expression flows, their own: `movements`, `spoken_reply`, `emotion`, ...). A developer adds a field; a non-coder cannot (Q07-6, Q08-6). The typed `FlowState` stays; a data file, the **catalog of fields**, describes it (name, schema piece, domain type), and every `reads` and `writes` is checked against it. The answer schema of a step is a combination of the existing schema pieces (the `SCHEMAS` of the phase files today).

### 3.2 What a step looks like

```json
{
  "schema_version": 1,
  "name": "draft_writer",
  "kind": "llm",
  "legacy_id": 7,
  "prompt": { "file": "prompts/7_drawf_writter.txt" },
  "answer": { "pieces": ["user_goal"], "required": ["user_goal"] },
  "reads":  ["message", "user_goal", "task_category", "actions", "constraints"],
  "writes": ["user_goal"],
  "data":   { "reads": ["public"] }
}
```

- `kind: "llm"` is one call; `"llm_per_action"` is one call per planned action (`for_each: "actions"`, Q08-7: the loop is a JSON setting, not code); `"code"` names a Python function registered in `application/steps/` (the motion validator, the gesture builder).
- `data` is **reserved and not enforced** (Q07-16): the step says what kind of data it reads, a model will say what it may receive, and the later data policy has one place to apply.
- The prompt may be a file or an inline text (Q06-14); `legacy_id` is the old phase number, kept as a label for metrics (Q07-9).
- The worker, the MCP operator and the data engineer (phases 4 to 6) are `llm_per_action` steps run by one composite step, `action_executor`, which keeps today's dependency ordering of the actions; it is the first test of whether the JSON is expressive enough.

### 3.3 What a flow looks like

```json
{
  "schema_version": 1,
  "name": "special",
  "steps": [
    { "step": "triage_specialist",         "pause_if": "needs_user_input", "retry_on_status": true },
    { "step": "project_manager",           "pause_if": "needs_user_input", "retry_on_status": true },
    { "step": "safety_quality_gatekeeper", "pause_if": "needs_user_input", "retry_on_status": true },
    { "step": "action_executor" },
    { "step": "draft_writer" },
    { "step": "editor_in_chief",           "retry_on_status": true }
  ],
  "on_pause":  "user_clarification",
  "on_resume": "answer_checker",
  "result_from": "editor_in_chief"
}
```

- The conditions (`needs_user_input`, `retry_on_status`, `has_reply`, ...) come from a **fixed list of names** a developer writes in Python; a flow cannot invent one (Q07-2).
- `on_pause` and `on_resume` declare what today is hard-wired in `engine/pipeline.py` (phases 99 and 9): a flow with no step that can ask carries neither.
- The **result of a flow is the `Response` of its last step** (`result_from`, Q09-1, Q07-5).
- The triage of `special` and `dynamics` **always runs** (owner, review of PR-005, 2026-11-02). There is no `skip_if`. A client may ask any profile after any other, including `identification` and then `special`; the second triage then runs. The service neither prevents it nor reports it: knowing which steps each profile has is the **client's** knowledge (owner, 2026-11-02).

### 3.4 What a profile looks like

```json
{
  "schema_version": 1,
  "name": "special",
  "about": "Triage, plan, check, execute with every MCP server, write, edit. Standalone: it does its own triage.",
  "token_sha256": "<hex of the SHA-256 of the token; never the token itself>",
  "flow": "special",
  "inputs": { "requires": [], "accepts": [] },
  "default_return": "text",
  "models": "claude_mixed",
  "tools": { "servers": ["dynamics_microservice"] },
  "settings": { "history_turns": 6, "max_mcp_calls_per_message": 5 },
  "overrides": {
    "draft_writer": { "models": ["claude-sonnet-5-5", "claude-haiku-4-5"], "prompt_append": { "text": "Answer in the user's language." } }
  },
  "tested": null
}
```

- **Either `flow` or `steps`** (an ordered list of step names written in the profile; Q06-1). Both at once is an error.
- `models` names a model set, or is an ordered list of ids (section 5).
- `overrides` is keyed by step name and may carry `models`, `tools`, `prompt_replace` and `prompt_append`.
- `token_sha256`: the client sends the plain token, the service hashes and compares in constant time; the token is **a check against a mistake**, not access control (Q08-8), and is never written to a log.
- `tested` is a note (`"2026-11-02"`), filled by the real-run command (section 10); a profile never run says `null`.

## 4. How a request is resolved

Order, for every request:

1. `profile` absent: `default`, no token. Present: the profile must exist and its `token` must hash to `token_sha256`. **Unknown profile and wrong token give the same answer**, `INVALID_PROFILE` (a generic message, 401/403); the real reason is only in the log; profiles are never listed (Q07-15, Q06-20).
2. A run is paused in the session? See section 6.
3. `inputs` must contain every required field, validated with the same schemas as an LLM answer; a missing one is `MISSING_INPUT`, before any model call (Q09-1).
4. The flow of the profile runs on a state built from `message`, the session history and `inputs`.
5. The `Response` of the last step is appended to the session list (section 7) and the answer is built (section 6).

## 5. Precedence

| What | Rule | Source |
|---|---|---|
| **Models** | the **most specific value replaces** the broader one, and the whole ordered list is replaced. From most to least specific: `profile.flows.<flow>.steps.<step>.models`, `profile.overrides.<step>.models`, `profile.flows.<flow>.models`, `profile.models` (a list or a model set), the step's own default. *(Dated note 2026-11-02, T-05.5: the first level, a step in one flow, was added to the other four so the same step can have two models in two flows, Q07-10.)* A model set may be named at any level (Q07-11). | Q07-10, Q07-11 |
| **Fallback** | the list **is** the fallback: the first model answers; when it is out of capacity (ADR-014: wait, then the next one) the next is tried. Profile, flow and step may each carry a list, replaced as above. | Q06-23, Q05-13 |
| **Tools** | the **narrowest limit wins**: the tools a step may use are the intersection of what the profile, the flow and the step allow (nothing set = no limit at that level). A tool outside is **neither shown to the model nor callable** (Q06-11). A profile names a whole server or single tools, as `server.tool`; a bare name two servers share is an error (Q06-12, Q07-19). | Q06-10 |
| **Prompts** | the most specific replaces; a profile may **replace** a step's prompt (only if the answer schema is the same) or **append** to it; inline text or a file (Q06-13, Q06-14). The reply language follows the user (Q06-15). | |
| **Settings** | profile, else the environment default (`AI_AGENT_HISTORY_TURNS`, `AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE`, timeouts); the retry settings stay global (Q06-22 B). | |

Environment variables **no longer override models**: `AI_AGENT_MODEL_PHASE_<n>` and `AI_AGENT_FALLBACK_MODELS` are removed (Q05-17); keys and URLs stay in the environment. A model change is a file change and a redeploy (Q05-14: nothing changes while the service runs).

## 6. The API

Written in `docs/api/api.md` as part of stage S2. The vendored `contracts` wheel does not have the new fields yet: ai-agent reads them through its **own extended request model** (Q08-9 B) until the owner changes the `contracts` repository (Q06-16). The profile and the token travel with **every** `/session/message`, in the body, and never in a log; `/session/start` needs none.

| Request field | Meaning |
|---|---|
| `profile`, `token` | the profile asked, and its token (absent: `default`) |
| `inputs` | optional object: the `Response` of a previous profile, or the fields the profile declares (`reply` and the user's message for `gesture`) |
| `return` | `"text"` (only `response`, as today) or `"full"` (also `output`); a profile may set `default_return` (`identification` sets `"full"`), the client has the last word (Q09-2) |
| `pause_id` | the id of the question being answered |
| `client` | a name for the metrics, trust-based (Q06-19) |

| Answer field | Meaning |
|---|---|
| `response`, `directives`, `awaiting_user_input`, `flow` | as today |
| `profile` | the profile that ran |
| `output` | the `Response` of the last step, only when `return` is `"full"`; `tokens_usage` and `raw` never travel (assistant's addition, section 12) |
| `pause_id` | only when `awaiting_user_input` is true |
| `discarded_pause` | only when a paused run was discarded |

A request with none of the new fields gets exactly today's answer.

**A run that asked the user a question** (Q09-3). The service issues a `pause_id`; the client sends it back with the answer.

| Request | Result |
|---|---|
| `pause_id` present, same profile, run still paused | it is the answer: phase 9 judges it (answered, confirmed, declined, stop, not an answer) and the step that waited runs again, as today; the id is consumed |
| `pause_id` present, another profile | `PROFILE_MISMATCH`; the run stays paused |
| `pause_id` unknown or used | `PAUSE_NOT_FOUND`; the client treats it as a new message |
| no `pause_id` while a run is paused | a new message: the paused run is discarded and logged, the answer says `discarded_pause: true` |

One paused run per session; lost on restart (ADR-009). `inputs` is ignored on a resume; the token is still checked.

**Which profile next** is the client's rule, written in `docs/api/api.md` so it does not live only in Brain: `task_category.domain` of the `identification` output: `communication` -> `chat`, `movement` -> `movement`. Any other domain: `special` (or `dynamics`). These two have their own triage, so after `identification` they classify again; the service allows it and says nothing, and a client that wants to avoid the extra call asks them directly. The table is the client's choice, not a rule of the service. `gesture` is asked with the reply and the user's message, never with the identification result.

## 7. Sessions and history

The session keeps a **list of `Response` objects, one per request**. The `user_goal` of each holds the input and the output of that request; a prompt reads the last N entries (`history_turns`) and takes the input and the output from each `user_goal` (Q09-4). This replaces `user_session.remember(message, reply)` (`application/service/session_service.py`). Two checks, both in `assemble()`: the final result of every profile carries a `user_goal` with input and output (the field is optional today), and a profile that ends in a code step with no `Response` (`gesture`) adds no entry. The history is the session's own copy and never comes from `inputs`.

## 8. The files and the layout

```text
ai-agent/
  profiles/        JSON, one per profile            (new)
  flows/           JSON, one per flow               (new)
  step_defs/       JSON, one per step               (new)
  model_sets/      JSON: the ten tables of step_models.json  (new)
  mcps/  prompts/  schema/                          (as today; per-profile prompts in prompts/profiles/<name>/)
  config/          catalog, prices, budget, data_policy (reserved), catalog of fields
  application/
    engine/        pipeline, runner, assemble(), hooks      (no knowledge of any flow)
    steps/         the Python of `code` steps and the registry of named functions and conditions
    ports/         ConfigSourcePort and the others as today
  domain/ infrastructure/ composition_root/          (as today)
```

Q07-20 B: the code stays under `application/`; the data folders are at the root. `step_defs/` (not `steps/`) avoids two folders with one name. This renames many paths (imports, tests, docs, the golden): **it is stage S1 and changes no behaviour**.

**Sources** (Q07-17). Everything is read **once at start** through `ConfigSourcePort` (`load_profiles`, `load_flows`, `load_step_defs`, `load_model_sets`, `load_prompt`), by a first adapter that reads these folders. Later adapters (SQL, S3, LangChain services) change nothing else: the data is plain (no Python inside a flow or a profile), every file carries `schema_version`, and the Python of `code` steps stays in the repository. No hot reload.

## 9. Validation: what makes it plug and play

`assemble()` builds the whole agent from the snapshot at start (and in `scripts/check_agent.py`, and in a test). Errors (Q06-6: all four are errors; the safety gate itself is optional, like every step, Q05-12):

| Check | Example |
|---|---|
| every name exists (step, flow, model, model set, tool, condition, hook), no unknown key | `profiles/special.json: unknown step 'safty_gate'` |
| a step reads a field that no earlier step, no `inputs` and no initial value provides | `special: 'draft_writer' reads 'actions' but nothing before it writes it` |
| no step produces the final text (the flow has no `result_from`) | `chat: no result_from` |
| a model cannot do what the step needs (a custom schema is run through the rules of **every** model in the lists, Q07-8; Claude's nesting limit, ADR-013) | `claude-haiku-4-5 cannot run 'project_manager': nesting 4 > 3` |
| the final result of the profile has a `user_goal` with input and output (section 7) | |
| `token_sha256` present for every profile but `default` | |

**When a profile is wrong** (Q07-18 C): in production the service starts, the wrong profile is **disabled** and logged at ERROR (its clients get `INVALID_PROFILE`) and the others work; in the tests and in `scripts/check_agent.py` the same error **stops** (a pull request cannot add a wrong profile). MCP tool names are checked against a **snapshot** of the tools (Q07-19 C, as the contract snapshot of Q03), not against a live server at start.

`scripts/check_agent.py --explain <profile>` prints the assembled agent: steps in order, model and its source for each, tools, prompts, and the cost of a full plan (one table per profile, replacing the three generated tables, Q07-21 A).

## 10. Metrics, tests and the first real use

- **Metrics and Langfuse.** One record per LLM call with `profile`, `flow`, `step`, `model`, `client`, tokens and cost, and the **hash of the assembled profile** in the log and as a tag; a cost per message (Q06-26 B, Q07-27). Totals by any key are computed from the records. No log, metric or span holds a tool argument or answer, nor a token (`CLAUDE.md`).
- **Golden file** (Q09-7). One block per profile `identification`, `chat`, `special`, `movement`, `gesture`. Each request is identical to today's request of the same step; the block of `special` is today's identification request followed by today's special requests (the sequence is new, each request is not). `default` and `dynamics` are tested with mocks, with no golden.
- **Real runs** (Q06-27, Q08-5). `scripts/run_profile.py <profile>` runs a small fixed set of messages (a greeting, a question, a plan, a movement, a Dynamics question, a message in Spanish) on the real models, saves the answers in `tests/output/` and writes `tested: <date>` in the profile; it costs a few cents and the owner decides when to run it.
- **The acceptance run of the first stage that changes behaviour (S2)** (Q08-12, Q09-9): profile `special`, message "Dime el estado de los pedidos del cliente CL-1001", models `claude_mixed`, with the Dynamics tools. It needs the Dynamics service running; if it is down that day the run records the planner's answer without the tool and is **not** a pass.

## 11. Stages (Q06-29 A, adapted) and epics

Each stage ends with the suite green and a written acceptance.

| Stage | Work | Behaviour change | Acceptance |
|---|---|---|---|
| **S1** | the layout of section 8; the step registry (`catalog.py` reads it); `test_orchestration_layout.py` rewritten for the new folders | none | golden file byte-identical |
| **S2** | `ConfigSourcePort` + file adapter; model sets from `step_models.json`; profiles `identification`, `chat`, `special`, `movement`, `gesture`, `default`, `dynamics` and the old ten as generic profiles (`_unverified/` until tested, Q06-9, Q07-12); `assemble()` and its checks; the API fields, errors and the `pause_id`; the session list of `Response`; the service stops routing | the API (new fields; the service no longer routes) and the history format | golden identical per profile; the acceptance run of section 10; **adding a profile is one file** |
| **S3** | flows as JSON; `on_pause`/`on_resume`; named conditions; `action_executor` as a composite step | none | golden identical |
| **S4** | tool scoping (profile, flow, step); the planner is shown only the allowed tools | tools shown to the model | a profile limited to one tool cannot call or see another |
| **S5** | prompts per profile (replace, append, inline) | prompts of the profiles that use it | a profile with an appended prompt sends it; the golden of the others is identical |
| **S6** | metrics by profile, flow, step, model, client; the profile hash; reserved data fields | metrics | a run shows every key |
| **S7** | every step converted to a JSON declaration; the `check_agent` and `run_profile` commands; `docs/models/*` regenerated per profile | none | golden identical; **adding a step is one JSON file and a prompt** |

Epics: **T-05 Structure** is S1 to S7. **T-06 Redesign** (after T-05) is the new flows of Q08-3, new steps (for example a tool caller for a flow with no planner), refined prompts and the new robot profiles; its acceptance is the fixed set of messages run on real models, compared with T-05's answers, and the owner reads the prompts (Q08-4, Q08-5). Separating them means a bad answer after T-06 has one obvious cause.

Documents to update, per stage and in the same change (`CLAUDE.md`): `architecture.md`, `api.md`, `requirements.md`, `environment-variables.md` (the removed variables), `schemas-and-prompts.md`, `monitoring.md`, `security.md` (tokens, what reaches Langfuse), `deployment.md`, `README.md`, `.env.example`, the task board and `ORDER.md`, a new ADR-015 (proposed together with this text) and a dated note on ADR-003, ADR-004 and ADR-014 when they are changed.

## 12. Risks, and the assumptions I made (veto them)

| Risk (owner's list, Q08-11: all of them) | How it is handled |
|---|---|
| The robot stops moving until Brain is updated | Accepted (section 2). `movement` and `gesture` exist from S2; the chaining rule is in `api.md`. Nothing is in production. |
| The golden file changes without anyone noticing | One block per profile; `UPDATE_GOLDEN=1` stays a deliberate act; S1, S3 and S7 must leave it identical. |
| A profile costs far more than expected | `check_agent --explain` prints the cost of a full plan per profile; no limit is enforced (Q05-11). |
| A profile reaches business data it should not | Only `special` and `dynamics` have the Dynamics tools (Q09-5 B); `default` has none; tools are the intersection of the three levels; tokens; `data` fields reserved for the policy of Q07-16. Langfuse still receives prompts and answers (`CLAUDE.md`). |
| A non-coder's JSON mistake reaches production | `assemble()` checks, strict in tests and `check_agent`, one profile disabled (not the service) in production, every change is a reviewed pull request and a redeploy (Q06-21). |
| The structure is so general that a simple change takes ten files | Acceptance of S2 and S7: a profile is one file, a step is one JSON file and a prompt. |

**Assumptions I made, not asked. Each is easy to change.**
1. `default` is `identification` + planner + gate + worker + writer + editor, **without** the MCP operator and the data engineer, because with no tools they have nothing to call (Q09-5 B, Q08-3).
2. **Decided in the review of 2026-11-02:** `special` and `dynamics` have the triage as their **first step** (as the table of Q08-3 says), so they work standalone. This changes Q09-7: `special` is no longer identical to today's special flow, it is today's identification step followed by today's special steps. The triage always runs and takes no `inputs`. After `identification` the client may call **any** profile; a second triage then runs, with no error and no warning from the service (section 3.3). `api.md` lists the steps of every profile so the client can choose knowingly.
3. `triage` is called `identification` (Q09-1); profile names are snake_case, so `robot-triage` is written `robot_triage` and exists only if its prompts differ from the generic ones (Q09-8).
4. `tokens_usage` and `raw` of a `Response` are never returned in `output` and are ignored in `inputs`: they describe the cost of one internal call and `raw` may hold the model's unfiltered text.
5. The `discarded_pause` field and the rule "a request with no `pause_id` discards a paused run" are mine (Q09-3); the owner agreed to the rule.
6. The motion and expression flows keep their own state classes (`MotionFlowState`, `ExpressionFlowState`); their fields go into the catalog of fields (section 3.1).
7. Q09-10 was left empty: I read it as nothing further.

## 13. Not in this proposal

- The data policy itself (Q07-16: later; the fields are reserved).
- A limit of cost at run time, hot reload of any file, a `GET /profiles` list (refused, Q06-20), profile inheritance (`extends`, Q06-8 B).
- Changing any prompt, schema or message in T-05 (that is T-06).
- The change of the `contracts` repository and of Brain.
