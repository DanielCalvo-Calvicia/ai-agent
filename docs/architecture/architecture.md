# Architecture

How ai-agent works, from the HTTP request to the LLM call and back. Written from the code on 2026-10-06 (after the
four-flow redesign). When this file and the code disagree, the code is right: fix this file.

Related: [`schemas-and-prompts.md`](../rules/schemas-and-prompts.md) (the JSON Schemas and prompts the phases use),
[`environment-variables.md`](../configuration/environment-variables.md) (every setting), [`debugging-the-flow.md`](../operations/debugging-the-flow.md).

## 1. The big picture

ai-agent is the "mind" of OBLIVION. It receives what the user said (text), decides, and returns a structured answer:
what to say, which arm movements to run, and whether it is waiting for the user. **It never controls hardware** and
never calls another service except the LLM providers and MCP tool servers. Brain acts on its answer.

```text
POST /session/message
   -> SessionFastAPI            infrastructure/inbound/http/fastapi.py   (HTTP <-> DTOs, runs the flow in a worker thread)
   -> SessionService            application/service/session_service.py  (sessions, history, the run waiting for the user)
   -> MessageFlowService        application/service/message_flow_service.py   (one per message; owns the metrics)
   -> ProfileRunner.run()       application/engine/profile_runner.py   (ONE profile: its flow, its models, its MCP servers)
        the profile of the request (`default` when it names none) names one flow:
           identification -> triage                                                      chat -> draft writer, editor
           special, dynamics, default -> triage, project manager, safety gate, action executor, draft writer, editor
           movement -> motion planner, motion validator                                  gesture -> emotion reader, gesture builder
   -> FlowResult(reply, movements, paused, flow, state, gesture)

   -> MessageReceivedResponseDTO -> contracts AIAgentMessageResponse (response, directives, awaiting_user_input, flow)
```

Every flow is run by the same engine (`Pipeline`). A flow is only data: a name, its steps, and how to build its result.
The engine knows no particular flow, and the flows never call each other. **The service does not move a message from one flow to the next
any more** (T-05.7, PR-005 section 2): the client does, by asking one profile after another (section 4.1).

## 2. The folders

```text
composition_root/main.py          builds the app (run this one)
application/
  inbound/{ports,dto}/            what the HTTP layer and the services implement and exchange
  outbound/ports/                 LLMOutboundPort, McpToolsPort (and the signal a tool failure for good leaves for the step loop), UsageReporterPort (LLM calls and, optionally, MCP tool calls), ConfigSourcePort (profiles, flows, step declarations, model sets and prompts, read once at start; T-05.4)
  service/                        session_service, message_flow_service, user_session (the session keeps one `HistoryEntry` per request: `engine/state/history.py`)
  system_prompts/general.py       builds the system message of a phase
  flows/  steps/  engine/         the agents (section 3 to 8); engine/ holds state/ and support/
profiles/ flows/ step_defs/ model_sets/   data folders of PR-005, empty until their tasks (T-05.4 onward)
domain/                           pure data (section 9)
infrastructure/                   adapters: inbound HTTP, outbound LLM, MCP, usage (section 10)
prompts/  schema/  config/  mcps/ data files the code reads (see rules/schemas-and-prompts.md and configuration/environment-variables.md)
scripts/split_schemas.py          builds the schema tree from schema/response/*/full.schema.json
tests/                            pytest (all mock-based) and tests/manual (real LLM / MCP, costs money)
docs/                             this documentation
```

Dependencies point inward: `domain` imports nothing of the application; `application` never imports `infrastructure`;
`composition_root` is the only place that knows every layer.

## 3. `flows/` (files), `application/steps/` and `application/engine/`

Four folders, each with one job (until 2026-11-02 they were the five folders of `application/orchestration/`, T-05.3; since T-05.12 the flows are JSON files at the root and `application/flows/` is gone). The dependencies go one way and `tests/test_orchestration_layout.py` keeps it so:

```text
flows/ (root)   WHAT each flow is          one JSON file per flow: its steps in order, its pause and retry rules, its hooks and the step its result comes from
steps/          the steps (the phases)      one phase per file, constants first; the registry; the catalog; the shape of a phase; `conditions.py`, `hooks.py` and `build.py` (the names a flow file may use); the action executor
engine/         HOW any flow runs           Pipeline, Flow, `flow_file.py` (a flow file -> a Flow), `profile_runner.py`, PhaseRunner, clarification, answer check, `config_snapshot.py` (the configuration read once through `ConfigSourcePort`); knows no particular flow
engine/state/   WHAT travels through a run  FlowState, MotionFlowState, PausedRun, FlowResult
engine/support/ shared helpers              model choice, metrics, failures, schemas, action tree, MCP server list (a server with no tools is left out), clock
```

`engine` never imports the steps of one flow (the flow files name them and the registry finds them); `steps` never import the engine (only its base, `state` and `support`);
`state` and `support` are the base (`support` reads only `steps.catalog`).

## 3.1 Assembling the agent (T-05.6)

`engine/assemble.py` builds the whole agent from the configuration snapshot (`engine/config_snapshot.py`: profiles, flows, step declarations, model sets and the
catalog of fields `config/state_fields.json`, read once at start) and refuses what cannot work. Every problem names its file and its key. At start a profile with a
problem is **disabled** and logged at ERROR (`Configuration problem`, `Profile disabled`) and the others serve; `scripts/check_agent.py` and the tests stop on the first
problem (`Agent.raise_on_errors`). It checks: unknown names and keys; `flow` xor `steps` in a profile; that every step reads only what an input, an `initial_state` or an earlier step
provides (the fields are those of the catalog, which a test keeps equal to the state classes); that a flow has a `result_from` and that its result writes `user_goal` (unless it is plain
code); the models of every list (a custom answer schema must pass the rules of Claude); the token (`token_sha256`, 64 hex characters; the message never repeats it); and the tool
names (`server`, `server.tool` or a bare name that only one server has). **Until flows and steps are files (T-05.12, T-05.16)** a profile may name a Python flow and a step with no
declaration: the checks that need `reads` and `writes` skip them. Nothing serves a profile yet (T-05.9): the service still has one agent.

## 3.2 What a session remembers (T-05.8)

A session keeps a list of `HistoryEntry` (`engine/state/history.py`), one per request: `message` (the user's words), `reply` (what was answered) and `response` (the
structured `Response` of the run, `FlowState.as_response()`: the fields of the state at the end of the run, the other side of `load_from`). `UserSession.history` derives
the messages the steps read from them (a user message, then its reply when there is one), so `history_as_dicts()` and `message_with_history()` give exactly what they gave when the
session kept text pairs. `AI_AGENT_HISTORY_TURNS` is the number of **requests** kept (it was 2 x messages). A request adds an entry only when its run has a `user_goal`
(`response_of`): the `gesture` profile and a movement nobody classified add none (PR-005 section 7). `user_goal` holds a summary and the expected outcome, not the user's words, and a
question to the user is a reply that is in no `user_goal`, so the entry keeps the words and the reply next to the `Response` (a deviation from Q09-4, which assumed `user_goal`
held both). The history is the session's own copy: it will never be read from the `inputs` of a request (T-05.9). Entries are never logged.

## 4. The four flows

| Flow | File | Steps | Answers | LLM calls |
|---|---|---|---|---|
| `identification` | `flows/identification.json` | triage | nothing: its `Response` is what the client reads (`default_return: full`) | 1 |
| `conversation` | `flows/conversation.json` | draft writer, editor | a plain reply | 2 (3 with identification) |
| `special` | `flows/special.json` | project manager, safety gate, action executor, draft writer, editor | a reply after planning and executing | 5 or more, plus one per action |
| `movement` | `flows/movement.json` | motion planner, motion validator (plain code) | movements to run and a short spoken line | 1 (2 with identification) |

### 4.1 One profile per message, and the client's chain (`engine/profile_runner.py`)

The service runs the flow of **one profile** per message (`ProfileRunner.run`): the profile gives the flow, the models (its `ModelResolver`) and the MCP servers
(`tools`, see section 4.2: the tools a step may use are those every level allows). Nothing routes. The
**client** chains the profiles, and `tests/brain_chain.py` models that chain for the tests:

```text
identification(message)                      -> the Response (the classification); stops here if the triage asks the user
domain = task_category.domain
  communication -> chat(message, inputs=that Response)       movement -> movement(message)       anything else -> special(message)
reply -> gesture(reply, message)             (not after movement: the user asked for movements, the robot does those)
```

- `SessionService` resolves a request (T-05.9): the profile and its token (`engine/profile_access.py`: SHA-256 compared in constant time; one refusal for an unknown profile and a wrong token), the question it answers (`pause_id`), the `inputs` (`engine/profile_inputs.py`: only the fields the profile takes, read with the LLM-answer mapper) and `return`; then `ProfileRunner.run(..., inputs=...)`. A request with no profile runs `default`.
- `special` and `dynamics` start with their own triage: a client that asks `identification` and then `special` classifies twice, and the service does not report it.
- A run that stopped to ask the user is resumed by the next message **of the same profile** (`PausedRun.flow`); another profile gets `ProfileMismatch` (T-05.9 turns it into `PROFILE_MISMATCH`).
- The domain comes from triage (`task_category.domain`, an enum of nine values, defined in the schema and in
  `domain/value_objects/llm_response/task_category/domain.py`). The triage prompt tells the model what each value means.

- `speak_movements` is Brain's setting. It is put in the movement flow's state for the message (also for a resumed run,
  so the answer to a question uses the setting of its own message).
- `FlowResult.flow` and `FlowResult.state` say which flow answered and with which state; `PausedRun.flow` says which flow
  stopped, so the next message is routed back to it.
- A message that mixes a reply and a movement ("hello, now raise your arm") goes to one flow only: the domain decides.

### 4.2 What each flow's result carries

| Flow | `reply` | `movements` |
|---|---|---|
| conversation, special | `user_goal.expected_outcome` after the editor | none |
| movement | the validator's refusal (always said), else the planner's `spoken_reply`; **empty** when movements go ahead and `speak_movements` is off. When nothing moves and nothing was refused (triage was wrong about the domain), the planner's line is said so the user always hears something | the validated sequence, in order (`degrees` is signed) |
| identification (paused) | the question for the user | none |

### 4.3 Pausing for the user

A step can say "the flow must stop and ask the user" (`pause_if`). The pipeline then writes the question (phase 99,
`engine/clarification.py`), saves a `PausedRun` (the state, the step that waited, why, the flow) in the session, and
returns the question with `awaiting_user_input = true`. The next message of the session is checked by phase 9
(`engine/answer_check.py`): an **answer** (the step that waited runs again with it), a **yes** or **no** (for a
confirmation of the safety gate), **not an answer** (the question is asked again, the run keeps waiting) or **stop**
(the run is forgotten). Pausing happens in: identification (triage), special (project manager, safety gate) and
movement (motion planner). Stop and decline end the run with a fixed sentence (`FlowResult.ended_early`).

### 4.2 Which tools a step may use (T-05.13)

A `tools` object (`{"servers": [...], "tools": [...]}`) can be set at five levels: the profile, `flows.<flow>` of the profile, the flow file, a step of the flow file (`{"step": ..., "tools": ...}`) and `overrides.<step>` of the profile. A level names whole servers and/or single tools (`server.tool`, or a bare name when only one server has it; assembly refuses a bare name two servers share); **a level that sets nothing sets no limit; `{"servers": []}` is no tool**. The tools a step may use are those **every level that is set allows** (the narrowest wins): a flow or a step that names a tool the profile does not allow gets nothing extra. The outer limit stays `allowed_tools` of `mcps/*.json`.

`Pipeline` builds each step with the servers and the tools port of its own scope (`application/outbound/ports/mcp_ports.py`: `ToolScope`, `ScopedTools`, `scoped`), so the planner and the MCP operator are **shown only** the allowed tools (and a server with none left is not shown). Each server descriptor of a limited scope carries the scope: the LLM adapter (`infrastructure/outbound/llm/tools.py`) exposes only the allowed tools to the model and runs them through `MCPToolExecutor.execute(..., scope=)`, which **refuses** any other and calls no server (outcome `not_found`, no try). The tools of the action executor are those of the step `action_executor` (its MCP operator runs inside it). `ProfileRunner.servers_of(profile, step)` says which servers a profile or a step may use. No log, metric or span holds an argument or an answer, as before.

### 4.3 The prompt of a step in a profile (T-05.14)

`overrides.<step>.prompt_append` and `prompt_replace` of a profile (a file under `prompts/` or an inline text) change the step's part of the system prompt; the generic rules, the capabilities and the date stay in front. The text is read at assembly (`AssembledProfile.prompts`: step -> `PromptOverride`, `engine/support/prompt_overrides.py`); `Pipeline` hands it to `PhaseRunner`, the only place a payload is built, which applies it in `run_phase` and `run_action` (so a step run once per action gets it too). A profile cannot change an answer schema, so a replacement keeps the format; the step must have a prompt and be one of the profile's flow. The clarification (phase 99) has a prompt that is part of its code and takes no override.

## 5. Phases

One phase per file under `application/steps/<folder>/`. Every file declares what it uses as constants at the
top (`PHASE_ID`, `STEP_NAME`, `MODEL_ENV_VAR`, `DEFAULT_MODEL`, `PROMPT_FILE`, `FORMAT_NAME`, `INTENT`, `SCHEMAS`, ...) and
each file registers itself in `steps/registry.py` (`register_step(__name__, kind)`: `llm`, `llm_per_action` or `code`; a name or a phase id used twice is an error) and `steps/catalog.py` reads the registry: the prompt loader, the model selection and the metrics take their tables from it.
`tests/test_phase_structure.py` enforces one phase per file and that every constant and file exists.

| Id | Step name | Folder / file | Used by | What it does |
|---|---|---|---|---|
| 1 | `triage_specialist` | `identification/triage.py` | identification | Classifies: `intent`, `user_goal`, `task_category` (its `domain` picks the flow) and `next_step` (asks the user when a detail is missing) |
| 2 | `project_manager` | `special/project_manager.py` | special | Splits the goal into a tree of `actions` (with subactions) and sets `next_step`. Sees the MCP servers and the history |
| 3 | `safety_quality_gatekeeper` | `special/safety_gate.py` | special | Fills `safety_and_validation`; may require a confirmation |
| 4 | `cognitive_worker` | `special/cognitive_worker.py` | special | Runs one non-MCP action given the outputs it depends on |
| 5 | `mcp_operator` | `special/mcp_operator.py` | special | Runs one `mcp_tool_call` action with the tools of the MCP servers (blocked if a confirmation is pending); it follows a `running` answer up once, within the 60 s the tool calls of a message share |
| 6 | `data_engineer` | `special/data_engineer.py` | special | Cleans the result of an MCP action |
| 7 | `draft_writer` | `common/draft_writer.py` | conversation, special | Writes the first user-facing answer into `user_goal.expected_outcome` (the reply read by `FlowState.final_text()` has stray model tags stripped); reads the user's own words (`user_message`) so it answers in their language, short and speakable |
| 8 | `editor_in_chief` | `common/editor_in_chief.py` | conversation, special | Polishes it; the reply is `user_goal.expected_outcome` |
| 9 | `answer_checker` | `common/answer_checker.py` | the engine | Reads the next message of a session with a saved run (answer / yes / no / not an answer / stop) |
| 20 | `motion_planner` | `movement/motion_planner.py` | movement | Writes the ordered movement list, `is_motion_request` and a short `spoken_reply`; asks the user when the arm or the degrees are missing |
| 21 | `motion_validator` | `movement/motion_validator.py` | movement | **No LLM call.** Valid arm and direction, degrees within limits, at most 20 movements and 3600 degrees in total; one bad movement refuses the whole sequence |
| 30 | `emotion_reader` | `expression/emotion_reader.py` | expression | Reads the feeling of an exchange (what the user said and what the robot answers): `emotion`, `intensity` 1 to 5 and up to 3 optional movements of its own |
| 31 | `gesture_builder` | `expression/gesture_builder.py` | expression | **No LLM call.** Builds the gesture: random movements shaped by the emotion (`domain/operations/gesture.py`), about as long as the speech, every arm back where it started; the motion validator checks it and a refused gesture is dropped |
| 99 | `user_clarification` | `common/user_clarification.py` | the engine | Writes the question for the user (plain text, temperature 0.7, 2000 tokens) |

A phase's answer is one JSON object built from the schema pieces it names in `SCHEMAS` (section 5.1 of
`rules/schemas-and-prompts.md`). Phases 4, 5 and 6 answer with the actions schema, one call per action.

The code defaults of `DEFAULT_MODEL` are Google models with a free tier: `gemini-3.1-flash-lite` for triage, data engineer, answer
checker, clarification and emotion reader, `gemini-3.6-flash` for the others ([ADR-012](../decisions/ADR-012-gemini-free-tier-default-no-github-models.md)). The model really used is chosen by
the model sets of `model_sets/` through `ModelResolver` (`engine/support/model_selection.py`, see `configuration.md`): an ordered list per step, the most specific value wins; the service runs on the set `proven` until profiles exist (T-05.7), which puts `gemini-3.1-flash-lite` on every step ([ADR-012](../decisions/ADR-012-gemini-free-tier-default-no-github-models.md)).

## 6. The engine

### 6.1 `Pipeline` (`engine/pipeline.py`)

`Pipeline(outbound_port, mcp_list, metrics, mcp_tools, flow=...)` builds the steps of a flow once and then
`run(message, history, paused, state)`:

1. a paused run is resumed (`_resume`); otherwise a state is created (or the caller's is used);
2. each step runs (`_run_step`: a step whose answer says `retry` or `error` runs again, up to `AI_AGENT_MAX_ATTEMPTS`,
   then an `AgentFailure`);
3. after a step, `pause_if` can stop the run (section 4.3); `Flow.jump_after` can jump to another step (no flow uses it today);
4. at the end `Flow.build_result(state)` makes the `FlowResult`, which the pipeline tags with the flow name and the state.

There is no default flow: `Pipeline` needs its `flow`.

### 6.2 `PhaseRunner` (`engine/phase_runner.py`): the only place an LLM payload is built

| Part | Value |
|---|---|
| System message | `0_generic_prompt.txt` + `capabilities.txt` + `CURRENT DATE AND TIME` + the phase prompt (`system_prompts/general.py`) |
| User message | one string: phase 1 the user text with the conversation so far; other phases `str()` of a dict of domain objects (the prompts are written against that format) |
| Response format | `json_schema` named by the phase's `FORMAT_NAME`, built by `object_schema(required, properties)` from the schema pieces (the actions' `$defs` are moved to the root) |
| Sampling | temperature 1.0, max tokens 10000 (phase 99: 0.7 and 2000) |
| Tools | none, except phase 5: the MCP servers, expanded by the adapter into the tools of each reachable `sse` or `streamable_http` server |
| Model | `PhaseRunner.models_for`: the ordered list of the step in this flow from the `ModelResolver` (a model set or a profile), else the code default |

`send()` asks the LLM, retries a failed call up to `AI_AGENT_MAX_ATTEMPTS` unless the error cannot get better
(`failure.worth_retrying`; after a lack of capacity it waits first, and then asks the rest of the step's ordered list once each, ADR-014), records the token usage in `SessionMetrics`, and raises an `AgentFailure` that says what
happened and in which activity (`PHASE_ACTIVITIES`).

### 6.3 Failures

`AgentFailure(category, phase_id)` carries what the user is told. Categories: connection, timeout, rate limit, auth, not
found, bad request, bad answer, unknown (`engine/support/failure.py`, `classify`). The session service answers with
`success = false`, an **apology that is always speakable** in `response` (what happened, in which activity and why), and
the technical reason in `message`. An unknown session answers `error_code = SESSION_NOT_FOUND`.

## 7. State

| Class | File | What it holds |
|---|---|---|
| `FlowState` | `engine/state/flow_state.py` | `message`, `history`, `answers` (what the user said when asked), and the sections the phases fill: `intent`, `user_goal`, `task_category`, `mcp_routing`, `actions`, `missing_information`, `constraints`, `safety_and_validation`, `next_step`. `take_over(other)` copies the shared fields from the identification state |
| `MotionFlowState` | `engine/state/motion_state.py` | `FlowState` plus `motion_requested`, `movements`, `motion_rejection`, `spoken_reply`, `speak_movements`. `as_motion(state)` narrows a `FlowState` for the movement steps |
| `PausedRun` | `engine/state/paused_run.py` | the saved run: state, step index, kind (`input` / `confirmation`), question, requested items, **flow** |
| `FlowResult` | `engine/state/paused_run.py` | `reply`, `paused`, `movements`, `flow`, `state`, `ended_early` |

Who writes what: triage loads `intent`, `user_goal`, `task_category`, `next_step`; the project manager `actions`, `next_step`
and the complexity; the safety gate `safety_and_validation`, `next_step`; the action executor the `output`/`error` of each
action; the draft writer and editor `user_goal` (and the editor `next_step`); the planner `motion_requested`, `movements`,
`spoken_reply`, `next_step`; the validator `movements` and `motion_rejection`. `constraints`, `mcp_routing` and
`missing_information` have schemas and domain objects but no phase writes them today.

## 8. The special flow's action executor (`steps/special/action_executor.py`)

An action is ready when its subactions and every action it depends on are settled (done or failed). It receives their
outputs. Its type picks the phase: `mcp_tool_call` goes to the MCP operator (phase 5) and then the data engineer (6), any
other type to the cognitive worker (4). Rules:

- execution order comes from `engine/support/action_tree.py` (parents after their subactions; unknown or circular dependencies
  are marked as failed, not run);
- `AI_AGENT_PARALLEL_ACTIONS=<n>` runs independent actions together (default 1; tool calls stay sequential);
- an MCP action is **blocked** while `requires_confirmation` is set (the run pauses at the safety gate first);
- the tool calls of one message may wait **60 s in total** (`MAX_TOOL_WAIT_SECONDS`, a budget the action loop opens for the run and the MCP adapter spends from: each call gets what is left, and with nothing left it is not made and answers a timeout). A query that is still running is followed up by the **operator step itself** (it may chain tool calls: `ai_sdk` allows 8 steps in one call), once, with `get_job_result`; it is not a second planned action;
- at most `AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE` (default 5, `0` = no limit) MCP actions run in one message, counted when an action starts (its retries do not count); the others fail with "the limit ... was reached, so only the first N could be done" and their dependants are skipped. The prompt wording that makes the reply say so is T-01.6;
- a failed action never stops the others: its dependants are skipped and the writer is told what worked.

## 9. `domain/`

Pure data, no file or network access, with one file per concept. `entities/` and `value_objects/` each have three
subfolders by what uses them:

```text
domain/
  entities/
    llm_request/    payload.py                       what is sent to a model
    llm_response/   action.py, response.py, tokens_usage.py   what comes back
  value_objects/
    llm_request/    message, model, model_catalog, max_tokens, temperature, top_p, reasoning,
                    response_format, tool
    llm_response/   intent/, user_goal/, task_category/, next_step/, safety_and_validation/,
                    missing_information/, constraints/, mcp_routing/, action/    (one folder per answer section)
    movement/       movement.py                      an arm movement; ARMS and DIRECTIONS
```

Value objects validate themselves in their `create_*` function (an empty id or an unknown enum value raises). The
response mapper builds them from the LLM's JSON, one function per section.

## 10. `infrastructure/`

| Folder | Job |
|---|---|
| `inbound/http/fastapi.py`, `responses.py` | `SessionFastAPI` (`/session/start`, `/session/message`, `/session/end`, `/health`, `/available`) and the response envelope from `contracts.api` |
| `outbound/llm/vercel.py` | `VercelAIAdapter.ask`: one stateless call (messages in, `Response` out) through `ai_sdk` |
| `outbound/llm/config.py` | `VercelAIConfig`: provider keys and URLs from the environment |
| `outbound/llm/provider_models.py` | domain model to `ai_sdk` model; a table of OpenAI-compatible routes (add a provider by adding a row) |
| `outbound/llm/anthropic_schema.py` | the schema a Claude model receives: `strict`, `additionalProperties: false`, the keywords Anthropic refuses removed, the action recursion unrolled to 3 levels ([ADR-013](../decisions/ADR-013-claude-through-sanitized-structured-outputs.md)) |
| `outbound/llm/tools.py` | `resolve_tools`: turns the MCP server list of phase 5 into real tools |
| `outbound/llm/response_mapper.py` | LLM JSON to `Response`, one function per section |
| `outbound/config/file_source.py` | `FileConfigSource`: reads `profiles/`, `flows/`, `step_defs/`, `model_sets/` (one JSON file each; a name that starts with `_` is skipped) and the prompt files; a file that cannot be read is reported by name, the others still load; a prompt name cannot leave the project. Nothing uses the snapshot yet (T-05.6) |
| `outbound/mcp/config.py` `load_tool_snapshot` | the MCP servers of `mcps/*.json` and the tools each lists in `allowed_tools`: what a profile may name (not the live list of a server) |
| `outbound/llm/anthropic_schema.py` `anthropic_schema_problems` | what Claude's endpoint would cut in a **custom** answer schema (a reference nested deeper than 3 levels); `assemble()` uses it, the schemas of the phases are not checked with it (their action recursion is unrolled on purpose) |
| `outbound/mcp/` | `config.py` (reads `mcps/*.json`, skips a server whose `${NAME}` url is not filled), `client_manager.py` (SSE or Streamable HTTP connection by `type`, forwards the trace headers, keeps `httpx`, `httpcore` and `mcp.client` out of the logs), `tool_catalog.py` (which server offers which tool, only those in its `allowed_tools`; a listing is kept, a failed one is not retried for 60 s; 10 s listing limit), `availability.py` (the optional `AI_AGENT_CHECK_MCP_<NAME>` check, log only), `tool_executor.py` (what the LLM adapter calls: a 30 s call limit, `AI_AGENT_MCP_CALL_TIMEOUT_SECONDS`, and one retry after a transport error or `retry_later`) |
| `outbound/usage/langfuse.py`, `prices.py` | optional cost reporting to Langfuse (section 11) |

## 11. Observability

- **Logging and tracing:** `shared_logging` (`init_logging("ai-agent")`, `TracingMiddleware`); messages are constant strings with
  keyword fields. The trace headers are forwarded to MCP servers.
- **Metrics:** `SessionMetrics` records tokens per phase, per model and per call for each message, and the MCP tool calls of the message (tool, outcome, duration, tries; never a value).
- **No value in any log, metric or span:** a tool argument or a tool answer is never logged, measured or traced; the libraries under the MCP client are kept at WARNING for that reason (see [monitoring](../operations/monitoring.md)).
- **Langfuse (optional, `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` set):** each message is a trace and each LLM call a
  `generation` named after its step, with model, tokens (thinking tokens included), cost, **and the payload sent and the
  answer received, which include the user's text and the prompts**. Use a Langfuse project you trust with them. A failure
  of the reporter never breaks a call.

## 12. Tests that guard the structure

| Test | Guards |
|---|---|
| `test_orchestration_layout.py` | the one-way dependencies of section 3 |
| `test_phase_structure.py` | one phase per file, every constant, every referenced file exists |
| `test_schema_tree.py` | the schema tree matches `full.schema.json`, the motion enums match `ARMS` / `DIRECTIONS` |
| `test_flow_golden.py` | every LLM call (model, prompts, messages, schema, sampling, tools) against `tests/golden/flow_golden.json`; since T-05.10 also one block per profile (`profile_identification`, `profile_chat`, `profile_special`, `profile_movement`, `profile_gesture`), and a test that the request of every step in a block is the request it had in the client's chain, only the model being the profile's |
| `test_profiles_mock.py` | `default` and `dynamics`, which run the steps of `special` and have no block: their tools, models and token |
| `test_plug_and_play.py` | a new profile is one file: a copy of the configuration in a temporary folder, one new file, the agent answers, nothing of the repository changed |
| `test_router.py`, `test_flows.py`, `test_motion_flow.py`, `test_resume.py` | the client's chain (`brain_chain.py`), flows, pausing and resuming |
| `test_profiles.py` | the seven profiles, one profile per message, the tools and models of each, the resume rule |
| `contracts/tests/e2e/` (workspace) | a real ai-agent process driven over HTTP and by Brain, with a scripted LLM |

## 13. How to extend it

- **A new phase:** its file (constants first, then `register_step(__name__, kind)`) in `steps/<folder>/`, a step in its flow. Nothing else lists it.
- **A new flow:** a file in `flows/` (its steps in order, `pause_if` and `retry_on_status`, `on_pause` and `on_resume` if a step can ask, `result_from`) and a profile in `profiles/` that names it; no Python while it uses the steps, conditions and hooks that exist (`scripts/check_agent.py` says what is wrong)
  (the client chooses the profile; the domain in the schema and the triage prompt only if it is a new one).
- **A new domain value:** `schema/response/general/full.schema.json` (then `python scripts/split_schemas.py --write`),
  `domain/value_objects/llm_response/task_category/domain.py`, the triage prompt, and the client's table from domain to profile (`docs/api/api.md`).
- **A new field in an answer:** the full schema, the prompt, the domain object and the response mapper, together
  (`rules/schemas-and-prompts.md`, section 4).
- **A new provider:** a row in `infrastructure/outbound/llm/provider_models.py`, its key and URL in `VercelAIConfig`, its
  models in `domain/value_objects/llm_request/model_catalog.py`. A provider with limits of its own on the schema (Claude) gets its own copy of it inside the adapter (`anthropic_schema.py`), never a change of the schemas of the phases.

If a change alters a prompt, a schema, a model (a model set or a profile too: a profile block pins the models of its profile) or a message format, regenerate the golden file on purpose
(`UPDATE_GOLDEN=1 python -m pytest tests/test_flow_golden.py`) and read the diff first.
