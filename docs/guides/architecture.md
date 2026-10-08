# Architecture

How ai-agent works, from the HTTP request to the LLM call and back. Written from the code on 2026-10-06 (after the
four-flow redesign). When this file and the code disagree, the code is right: fix this file.

Related: [`schemas_and_prompts.md`](schemas_and_prompts.md) (the JSON Schemas and prompts the phases use),
[`configuration.md`](configuration.md) (every setting), [`debugging_the_flow.md`](debugging_the_flow.md).

## 1. The big picture

ai-agent is the "mind" of OBLIVION. It receives what the user said (text), decides, and returns a structured answer:
what to say, which arm movements to run, and whether it is waiting for the user. **It never controls hardware** and
never calls another service except the LLM providers and MCP tool servers. Brain acts on its answer.

```text
POST /session/message
   -> SessionFastAPI            infrastructure/inbound/http/fastapi.py   (HTTP <-> DTOs, runs the flow in a worker thread)
   -> SessionService            application/service/session_service.py  (sessions, history, the run waiting for the user)
   -> MessageFlowService        application/service/message_flow_service.py   (one per message; owns the metrics)
   -> AgentRouter.run()         application/orchestration/flows/router.py
        1. identification flow   triage: what is this message?         (always)
        2. ONE of these, picked by task_category.domain:
              communication -> conversation flow    draft writer, editor
              movement      -> movement flow        motion planner, motion validator
              anything else -> special flow         project manager, safety gate, action executor, draft writer, editor
   -> for a conversation or special reply: EXPRESSION flow (emotion_reader -> gesture_builder), after the reply is final
   -> FlowResult(reply, movements, paused, flow, state, gesture)
   -> MessageReceivedResponseDTO -> contracts AIAgentMessageResponse (response, directives, awaiting_user_input, flow)
```

Every flow is run by the same engine (`Pipeline`). A flow is only data: a name, its steps, and how to build its result.
The engine knows no particular flow, and the flows never call each other: **only the router moves a message from one
flow to the next**.

## 2. The folders

```text
composition_root/main.py          builds the app (run this one)
application/
  inbound/{ports,dto}/            what the HTTP layer and the services implement and exchange
  outbound/ports/                 LLMOutboundPort, McpToolsPort, UsageReporterPort
  service/                        session_service, message_flow_service, user_session
  system_prompts/general.py       builds the system message of a phase
  orchestration/                  the agents (section 3 to 8)
domain/                           pure data (section 9)
infrastructure/                   adapters: inbound HTTP, outbound LLM, MCP, usage (section 10)
prompts/  schema/  config/  mcps/ data files the code reads (see schemas_and_prompts.md and configuration.md)
scripts/split_schemas.py          builds the schema tree from schema/response/*/full.schema.json
tests/                            pytest (all mock-based) and tests/manual (real LLM / MCP, costs money)
docs/                             this documentation
```

Dependencies point inward: `domain` imports nothing of the application; `application` never imports `infrastructure`;
`composition_root` is the only place that knows every layer.

## 3. `application/orchestration/`

Five folders, each with one job. The dependencies go one way and `tests/test_orchestration_layout.py` keeps it so:

```text
flows/    WHAT each agent is        one file per flow, the router, the registry, the action executor
phases/   the steps                 one phase per file, constants first; the catalog; the shape of a phase
engine/   HOW any flow runs         Pipeline, Flow, PhaseRunner, clarification, answer check; knows no particular flow
state/    WHAT travels through a run  FlowState, MotionFlowState, PausedRun, FlowResult
support/  shared helpers            model choice, metrics, failures, schemas, action tree, MCP server list, clock
```

`flows` use everything below; `engine` never imports a flow; `phases` never import the engine; `state` and `support`
are the base (`support` reads only `phases.catalog`).

## 4. The four flows

| Flow | File | Steps | Answers | LLM calls |
|---|---|---|---|---|
| `identification` | `flows/identification.py` | triage | nothing: its state is what the router reads | 1 |
| `conversation` | `flows/conversation.py` | draft writer, editor | a plain reply | 2 (3 with identification) |
| `special` | `flows/special.py` | project manager, safety gate, action executor, draft writer, editor | a reply after planning and executing | 5 or more, plus one per action |
| `movement` | `flows/movement.py` | motion planner, motion validator (plain code) | movements to run and a short spoken line | 1 (2 with identification) |

### 4.1 The router (`flows/router.py`)

```text
run(message, history, paused, speak_movements):
  if a run is waiting for the user (paused):
        resume the flow that stopped it (paused.flow); the message is its answer, nothing is identified again
        (if that flow is identification and it now finished, continue as a new message below)
  else:
        result = identification.run(message)
        if identification paused (triage needs a detail): return its question
  flow = FLOW_BY_DOMAIN.get(task_category.domain, special)
  state = flow.new_state(...); state.take_over(identification state)      # nothing is classified twice
  return that flow's pipeline.run(state=state)
```

- `FLOW_BY_DOMAIN`: `communication` -> conversation, `movement` -> movement. Any other domain, or none, -> special.
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

## 5. Phases

One phase per file under `application/orchestration/phases/<folder>/`. Every file declares what it uses as constants at the
top (`PHASE_ID`, `STEP_NAME`, `MODEL_ENV_VAR`, `DEFAULT_MODEL`, `PROMPT_FILE`, `FORMAT_NAME`, `INTENT`, `SCHEMAS`, ...) and
`phases/catalog.py` reads them: the prompt loader, the model selection and the metrics take their tables from it.
`tests/test_phase_structure.py` enforces one phase per file and that every constant and file exists.

| Id | Step name | Folder / file | Used by | What it does |
|---|---|---|---|---|
| 1 | `triage_specialist` | `identification/triage.py` | identification | Classifies: `intent`, `user_goal`, `task_category` (its `domain` picks the flow) and `next_step` (asks the user when a detail is missing) |
| 2 | `project_manager` | `special/project_manager.py` | special | Splits the goal into a tree of `actions` (with subactions) and sets `next_step`. Sees the MCP servers and the history |
| 3 | `safety_quality_gatekeeper` | `special/safety_gate.py` | special | Fills `safety_and_validation`; may require a confirmation |
| 4 | `cognitive_worker` | `special/cognitive_worker.py` | special | Runs one non-MCP action given the outputs it depends on |
| 5 | `mcp_operator` | `special/mcp_operator.py` | special | Runs one `mcp_tool_call` action with the tools of the MCP servers (blocked if a confirmation is pending) |
| 6 | `data_engineer` | `special/data_engineer.py` | special | Cleans the result of an MCP action |
| 7 | `draft_writer` | `common/draft_writer.py` | conversation, special | Writes the first user-facing answer into `user_goal.expected_outcome` |
| 8 | `editor_in_chief` | `common/editor_in_chief.py` | conversation, special | Polishes it; the reply is `user_goal.expected_outcome` |
| 9 | `answer_checker` | `common/answer_checker.py` | the engine | Reads the next message of a session with a saved run (answer / yes / no / not an answer / stop) |
| 20 | `motion_planner` | `movement/motion_planner.py` | movement | Writes the ordered movement list, `is_motion_request` and a short `spoken_reply`; asks the user when the arm or the degrees are missing |
| 21 | `motion_validator` | `movement/motion_validator.py` | movement | **No LLM call.** Valid arm and direction, degrees within limits, at most 20 movements and 3600 degrees in total; one bad movement refuses the whole sequence |
| 30 | `emotion_reader` | `expression/emotion_reader.py` | expression | Reads the feeling of an exchange (what the user said and what the robot answers): `emotion`, `intensity` 1 to 5 and up to 3 optional movements of its own |
| 31 | `gesture_builder` | `expression/gesture_builder.py` | expression | **No LLM call.** Builds the gesture: random movements shaped by the emotion (`domain/operations/gesture.py`), about as long as the speech, every arm back where it started; the motion validator checks it and a refused gesture is dropped |
| 99 | `user_clarification` | `common/user_clarification.py` | the engine | Writes the question for the user (plain text, temperature 0.7, 2000 tokens) |

A phase's answer is one JSON object built from the schema pieces it names in `SCHEMAS` (section 5.1 of
`schemas_and_prompts.md`). Phases 4, 5 and 6 answer with the actions schema, one call per action.

The code defaults of `DEFAULT_MODEL` are GitHub Models ids (a retired service). The model really used is chosen by
`AI_AGENT_MODEL_PHASE_<id>` or `config/step_models.json` (see `configuration.md`).

## 6. The engine

### 6.1 `Pipeline` (`engine/pipeline.py`)

`Pipeline(outbound_port, mcp_list, metrics, mcp_tools, flow=...)` builds the steps of a flow once and then
`run(message, history, paused, state)`:

1. a paused run is resumed (`_resume`); otherwise a state is created (or the router's is used);
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
| Tools | none, except phase 5: the MCP servers, expanded by the adapter into the tools of each reachable SSE server |
| Model | `model_for_phase`: env variable, then `config/step_models.json`, then the code default |

`send()` asks the LLM, retries a failed call up to `AI_AGENT_MAX_ATTEMPTS` unless the error cannot get better
(`failure.worth_retrying`), records the token usage in `SessionMetrics`, and raises an `AgentFailure` that says what
happened and in which activity (`PHASE_ACTIVITIES`).

### 6.3 Failures

`AgentFailure(category, phase_id)` carries what the user is told. Categories: connection, timeout, rate limit, auth, not
found, bad request, bad answer, unknown (`support/failure.py`, `classify`). The session service answers with
`success = false`, an **apology that is always speakable** in `response` (what happened, in which activity and why), and
the technical reason in `message`. An unknown session answers `error_code = SESSION_NOT_FOUND`.

## 7. State

| Class | File | What it holds |
|---|---|---|
| `FlowState` | `state/flow_state.py` | `message`, `history`, `answers` (what the user said when asked), and the sections the phases fill: `intent`, `user_goal`, `task_category`, `mcp_routing`, `actions`, `missing_information`, `constraints`, `safety_and_validation`, `next_step`. `take_over(other)` copies the shared fields from the identification state |
| `MotionFlowState` | `state/motion_state.py` | `FlowState` plus `motion_requested`, `movements`, `motion_rejection`, `spoken_reply`, `speak_movements`. `as_motion(state)` narrows a `FlowState` for the movement steps |
| `PausedRun` | `state/paused_run.py` | the saved run: state, step index, kind (`input` / `confirmation`), question, requested items, **flow** |
| `FlowResult` | `state/paused_run.py` | `reply`, `paused`, `movements`, `flow`, `state`, `ended_early` |

Who writes what: triage loads `intent`, `user_goal`, `task_category`, `next_step`; the project manager `actions`, `next_step`
and the complexity; the safety gate `safety_and_validation`, `next_step`; the action executor the `output`/`error` of each
action; the draft writer and editor `user_goal` (and the editor `next_step`); the planner `motion_requested`, `movements`,
`spoken_reply`, `next_step`; the validator `movements` and `motion_rejection`. `constraints`, `mcp_routing` and
`missing_information` have schemas and domain objects but no phase writes them today.

## 8. The special flow's action executor (`flows/action_executor.py`)

An action is ready when its subactions and every action it depends on are settled (done or failed). It receives their
outputs. Its type picks the phase: `mcp_tool_call` goes to the MCP operator (phase 5) and then the data engineer (6), any
other type to the cognitive worker (4). Rules:

- execution order comes from `support/action_tree.py` (parents after their subactions; unknown or circular dependencies
  are marked as failed, not run);
- `AI_AGENT_PARALLEL_ACTIONS=<n>` runs independent actions together (default 1; tool calls stay sequential);
- an MCP action is **blocked** while `requires_confirmation` is set (the run pauses at the safety gate first);
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
| `outbound/llm/tools.py` | `resolve_tools`: turns the MCP server list of phase 5 into real tools |
| `outbound/llm/response_mapper.py` | LLM JSON to `Response`, one function per section |
| `outbound/mcp/` | `config.py` (reads `mcps/*.json`), `client_manager.py` (SSE connection, forwards the trace headers), `tool_catalog.py` (which server offers which tool; cached, 10 s timeout), `tool_executor.py` (what the LLM adapter calls) |
| `outbound/usage/langfuse.py`, `prices.py` | optional cost reporting to Langfuse (section 11) |

## 11. Observability

- **Logging and tracing:** `shared_logging` (`init_logging("ai-agent")`, `TracingMiddleware`); messages are constant strings with
  keyword fields. The trace headers are forwarded to MCP servers.
- **Metrics:** `SessionMetrics` records tokens per phase, per model and per call for each message.
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
| `test_flow_golden.py` | every LLM call (model, prompts, messages, schema, sampling, tools) against `tests/golden/flow_golden.json` |
| `test_router.py`, `test_flows.py`, `test_motion_flow.py`, `test_resume.py` | routing, flows, pausing and resuming |
| `contracts/tests/e2e/` (workspace) | a real ai-agent process driven over HTTP and by Brain, with a scripted LLM |

## 13. How to extend it

- **A new phase:** its file (constants first) in `phases/<folder>/`, one line in `phases/catalog.py`, a step in its flow.
- **A new flow:** a file in `flows/` with its steps and result, its phase files, one line in `flows/registry.py`, and a line in
  `FLOW_BY_DOMAIN` in `flows/router.py` (plus the domain in the schema and the triage prompt if it is a new one).
- **A new domain value:** `schema/response/general/full.schema.json` (then `python scripts/split_schemas.py --write`),
  `domain/value_objects/llm_response/task_category/domain.py`, the triage prompt, `FLOW_BY_DOMAIN`.
- **A new field in an answer:** the full schema, the prompt, the domain object and the response mapper, together
  (`schemas_and_prompts.md`, section 4).
- **A new provider:** a row in `infrastructure/outbound/llm/provider_models.py`, its key and URL in `VercelAIConfig`, its
  models in `domain/value_objects/llm_request/model_catalog.py`.

If a change alters a prompt, a schema, a model or a message format, regenerate the golden file on purpose
(`UPDATE_GOLDEN=1 python -m pytest tests/test_flow_golden.py`) and read the diff first.
