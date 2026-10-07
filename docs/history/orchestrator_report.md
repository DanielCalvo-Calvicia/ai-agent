> **HISTORICAL (banner added 2026-10-01; the phase chain is now split into four flows, see `../guides/architecture.md`).** This report was written on 2026-09-21 from the code before the refactor, the flows split and the folder reorganisation: file paths, the single pipeline and the listed prompt/schema mismatches describe that earlier state. For the current design read `README.md` and `CLAUDE.md`.

# Orchestrator report

What the agent's orchestrator does today, phase by phase: what each phase receives, what it must answer, and what the code does with the answer. Written from the code, the prompts (`prompts/advanced/`) and the JSON Schemas (`schema/response/general/`) as of 2026-09-21. No real LLM was called, so "expects" means what the prompt, schema and code say, not what a model was seen to do.

Section 8 lists the places where prompts, schemas and code disagree. Read it before changing the flow. Three of them change what the agent can do at all.

## 1. Overview

```text
user message
   |
   v
 1 Triage -> 2 Project manager -> 3 Safety gate -> 4 Worker -> 5 MCP operator -> 6 Data engineer -> 7 Draft writer -> 8 Editor
                  |                     |
                  +---- pause? ---------+---> phase 99: write a question for the user, end of this message
```

- `Pipeline.run(message, history)` (`application/orchestration/pipeline.py`) creates a `FlowState`, runs the 8 steps in order, and after phases 2 and 3 checks whether to pause.
- The reply is `state.user_goal.expected_outcome` after phase 8 (empty string if missing). At a pause, the reply is the phase 99 question.
- Only the LLM decides. The code passes data between phases, runs the action tree, and executes MCP tools through the LLM's tool calls.
- Each user message is a fresh run. What carries over is the session history (last 6 exchanges), which only phases 1 and 2 read.

Call count for one message: `3` (phases 1-3) + one per non-MCP action + one per MCP action + one per action that has an output (phase 6) + `2` (phases 7-8). Two actions with outputs cost 9 calls. A pause after phase 2 costs 3 calls (2 plus the question).

## 2. How every LLM call is built

One place builds it: `PhaseRunner` (`phase_runner.py`, `_build_payload`).

| Part | Value |
|---|---|
| System message | `prompts/advanced/0_generic_prompt.txt` + blank line + the phase prompt. The generic prompt says: machine-to-machine, return exactly one JSON object, no prose, follow the schema, `next_step` is the only control signal. |
| User message | One string. Phase 1: the raw text. Every other phase: `str()` of a Python dict (see "Input format" below). |
| Response format | `{"type":"json_schema","json_schema":{"name": <per phase>, "schema": {"type":"object","required":[...],"properties":{...}}}}`, no `strict` flag. |
| Sampling | temperature 1.0, max tokens 10000, no top_p, no seed. Phase 99: 0.7 and 2000. |
| Tools | None, except phase 5: the MCP server list, expanded by the adapter into the real tools of each reachable SSE server. |
| Model | GitHub Models: `gpt-4.1-mini` for phase 1, `gpt-4.1` for the rest. Override with `AI_AGENT_MODEL_PHASE_<n>`. |
| Answer handling | `json.loads(text)` then `response_mapper.build_response` builds a domain `Response`. Fields the phase did not return are `None`. A failure anywhere raises and the whole message fails (no retry). |

### Input format (important)

The user message of phases 2 to 8 is a Python `dict.__str__()`, not JSON. Domain objects appear as their `repr`. Example of what phase 4 receives:

```text
{'action': Action(id=Id(value='1'), description=Description(value='Summarize the file'), action_type=ActionType(value='analysis'), mcp_context=None, dependencies=Dependencies(value=['0']), required_inputs=None, output=None, error=None, subtasks=None), 'user_goal': UserGoal(summary=Summary(value='...'), expected_outcome=ExpectedOutcome(value='...')), 'dependency_outputs': {'0': 'text of action 0'}}
```

The prompts describe these inputs as named fields ("action", "user_goal", ...). The names match the dict keys. The values are `repr` strings.

## 3. Shared state (`FlowState`)

| Field | Written by | Read by |
|---|---|---|
| `message` | start | 1 |
| `history` | start (session) | 1, 2 |
| `intent` | 1 | nobody |
| `user_goal` | 1, then 7, then 8 | 2, 4, 7, 8, final reply |
| `task_category` | 1 | 2, 7 |
| `actions` | 2 | 3, 4, 5, 6, 7, clarification |
| `next_step` | 1, 2, 3, 8 | pause check, 3, 8, clarification |
| `safety_and_validation` | 3 | 5 |
| `constraints` | nobody (always `None`) | 7, 8 |
| `mcp_routing`, `missing_information` | nobody | nobody |

`Action.output` and `Action.error` are also written in place by phases 4, 5, 6 and by the blocked-MCP rule.

## 4. Phases

### Phase 1: Triage specialist

- **Does:** classifies the request. Does not plan or solve. Decides if there is enough information.
- **Model:** `gpt-4.1-mini`. **Code:** `phases/triage.py`.
- **Input:** the message text. With history: `Conversation so far:\nuser: ...\nassistant: ...\n\nCurrent user message:\n<text>`.
- **Answer (all required):**

```json
{
  "intent": {"primary": "information_request", "secondary": [], "confidence": 0.9},
  "user_goal": {"summary": "Know tomorrow's weather", "expected_outcome": "A short weather forecast for the user's city"},
  "task_category": {"domain": "research", "type": "analysis", "complexity": "low"},
  "next_step": {"ready_to_execute": true, "status": "proceed", "recommended_action": "", "blocking_reason": ""}
}
```

  - `intent.primary`: `information_request | task_execution | content_generation | decision_support | clarification_request | system_operation`
  - `task_category.domain`: `software | data | writing | design | research | operations | communication | system`
  - `task_category.type`: `analysis | design | generation | modification | validation | classification | orchestration`
  - `complexity`: `low | medium | high`. `next_step.status`: `proceed | awaiting_user_input | awaiting_confirmation | retry | error | complete`.
- **Prompt rule:** if the request is ambiguous, `status = awaiting_user_input`, `recommended_action = ask_user_for_missing_information`, and a list of questions.
- **Applied:** everything the answer has is copied into the state (`load_from`). It starts the state.
- **Pause after it:** none. See finding F.

### Phase 2: Project manager

- **Does:** turns the goal into a recursive plan: actions with hierarchical ids (`"1"`, `"1.1"`), dependencies, type, `required_inputs` (only what only the user can give), and MCP details. Sets `next_step`: awaiting the user if any action has `required_inputs`.
- **Model:** `gpt-4.1`. **Code:** `phases/project_manager.py`.
- **Input:** `{'user_goal': ..., 'task_category': ..., 'available_mcp_servers': [<server dicts>]}` plus `'conversation_history': [{'role','content'}, ...]` when there is history. Each server dict is `{'name','type','config':{...}}` straight from `mcps/*.json`.
- **Answer (all required):**

```json
{
  "actions": [
    {
      "id": "1", "description": "Get the forecast", "action_type": "mcp_tool_call",
      "dependencies": [], "required_inputs": [], "output": "", "error": "",
      "mcp_context": {"server_id": "aws_microservice", "tool_name": "get_weather", "parameters": {"city": "Madrid"}},
      "subactions": []
    }
  ],
  "next_step": {"ready_to_execute": true, "status": "proceed", "recommended_action": "", "blocking_reason": ""},
  "task_category_complexity": "low"
}
```

  - `action_type`: `analysis | generation | transformation | decision | retrieval | clarification | mcp_tool_call`.
  - Every action must carry `mcp_context` (`server_id`, `tool_name`, `parameters`), used only for `mcp_tool_call`.
  - `subactions` is optional and recursive with the same shape. Subactions run before their parent.
- **Applied:** `actions` and `next_step` only. `task_category_complexity` is read and dropped.
- **Pause after it:** yes, if `next_step.status` is `awaiting_user_input` or `awaiting_confirmation`.

### Phase 3: Safety and quality gatekeeper

- **Does:** reads the plan and decides if it is sensitive (deletes data, irreversible, sends messages for the user, private data, risky changes) and if the user must confirm first. Must not change the plan.
- **Model:** `gpt-4.1`. **Code:** `phases/safety_gate.py`.
- **Input:** `{'actions': [Action(...), ...], 'next_step': NextStep(...)}`. Only top-level actions, each as a `repr`.
- **Answer (all required):**

```json
{
  "safety_and_validation": {"sensitive": false, "requires_confirmation": false},
  "next_step": {"ready_to_execute": true, "status": "proceed", "recommended_action": "", "blocking_reason": ""}
}
```

  If confirmation is required: `status = awaiting_confirmation`, `recommended_action` = what must be confirmed.
- **Applied:** both fields replace the state's.
- **Pause after it:** yes, same rule as phase 2. Also `requires_confirmation = true` blocks every MCP action in phase 5, even when `status` is `proceed`.

### Phase 4: Cognitive worker

- **Does:** produces the result of one non-MCP action, using upstream outputs. If the action has subactions, it should combine their results. No tools, no invention.
- **Model:** `gpt-4.1`, one call per action. **Code:** `ActionWalker.run_cognitive_worker`.
- **Walk:** for each top-level action in order: skip if `mcp_tool_call`, otherwise process its subactions first (same rule), then itself. `completed_outputs` maps action id to output.
- **Input:** `{'action': Action(...), 'user_goal': UserGoal(...), 'dependency_outputs': {id: text}}` plus `'subaction_outputs': {id: text}` when there were subactions. `dependency_outputs` only contains dependencies already in `completed_outputs`.
- **Answer:** the actions array, with one action (same fields as in phase 2) and its `output` filled:

```json
{"actions": [{"id": "1", "description": "...", "action_type": "analysis", "dependencies": [], "required_inputs": [],
              "mcp_context": {"server_id": "", "tool_name": "", "parameters": {}},
              "output": "the result", "error": ""}]}
```

- **Applied:** the code reads only `actions[0].output`. If present, `action.mark_success(output)` and the id goes into `completed_outputs`. If empty or missing, nothing happens (no error is recorded).

### Phase 5: MCP operator

- **Does:** runs one `mcp_tool_call` action through the MCP tools and returns the raw result in `output` (or the failure in `error`). Does not clean the result.
- **Model:** `gpt-4.1`, one call per MCP action. **Code:** `ActionWalker.run_mcp_operator`, `infrastructure/outbound/llm/tools.py`.
- **Blocked case:** if `safety_and_validation.requires_confirmation` is true, no LLM call is made. Every MCP action in the tree gets `error = "Execution blocked: requires user confirmation before running MCP tools."`.
- **Input:** `{'action': ..., 'available_mcp_servers': [...], 'safety_and_validation': ..., 'dependency_outputs': {...}}` plus `'subaction_outputs'`. Tools: the tools of every reachable SSE server (a stdio server offers none). The LLM calls them itself (`ai_sdk` tool loop, up to 8 steps) and then answers the JSON.
- **Answer:** same shape as phase 4, with `output` = raw result and `error` = message or `""`.
- **Applied:** only `output` is read (same as phase 4). The `error` the LLM writes is ignored. See finding H.

### Phase 6: Data engineer

- **Does:** cleans one action's `output` (removes HTTP headers, envelopes, request ids, wrappers, long traces) without summarizing or changing meaning.
- **Model:** `gpt-4.1`, one call per action that has an output, children first. **Code:** `ActionWalker.run_data_engineer`.
- **Input:** `{'action': Action(...)}` only.
- **Answer:** same shape as phase 4 with the cleaned `output`.
- **Applied:** replaces `action.output`. Runs on cognitive outputs too.

### Phase 7: Draft writer

- **Does:** writes the first user-facing answer from all outputs, following the constraints. Must not mention ids, phases or MCP.
- **Model:** `gpt-4.1`. **Code:** `phases/draft_writer.py`.
- **Input:** `{'user_goal': ..., 'task_category': ..., 'actions': [top-level Action(...) with outputs], 'constraints': None}`.
- **Answer:**

```json
{"user_goal": {"summary": "Know tomorrow's weather", "expected_outcome": "Tomorrow in Madrid will be sunny, around 24 degrees."}}
```

- **Applied:** `state.user_goal` is replaced. So the triage summary and the plan's goal are overwritten by whatever the writer returns.

### Phase 8: Editor in chief

- **Does:** polishes the draft (clarity, grammar, no new facts), applies formatting only if constraints ask, and finalizes `next_step`.
- **Model:** `gpt-4.1`. **Code:** `phases/editor_in_chief.py`.
- **Input:** `{'user_goal': ..., 'constraints': None, 'next_step': ...}`.
- **Answer:** `user_goal` and `next_step` (same shapes as above). `status = complete` when satisfied, `awaiting_user_input` when something is still missing.
- **Applied:** both replace the state's. **The reply is `user_goal.expected_outcome`.** `next_step` is not read afterwards.

### Phase 99: User clarification (not in the chain)

- **When:** after phase 2 or 3 when `next_step.status` is `awaiting_user_input` or `awaiting_confirmation`.
- **Collects:** `next_step.request_user_input` items, then every action's `required_inputs`. If that list is empty: `blocking_reason`, else `recommended_action`. If still empty: fixed English text `Additional information is required to proceed. Please provide more details.` and no LLM call.
- **Call:** plain text, no schema. System: "communicating directly with an end user... clear, friendly, concise, do not expose internal details". User: `The following information is required from the user:\n- item\n- item`.
- **Reply:** the LLM text becomes the reply of this message.

## 5. Control flow

| Signal | Used? |
|---|---|
| `next_step.status` = `awaiting_user_input` / `awaiting_confirmation` after phase 2 or 3 | Yes: pause and ask. |
| `next_step.status` = `proceed`, `complete`, `retry`, `error` | No. |
| `next_step.ready_to_execute`, `retry_action_id` | No. |
| `next_step` after phase 1 or 8 | No (phase 1's is overwritten by phase 2's, phase 8's is never read). |
| `safety_and_validation.requires_confirmation` | Yes: blocks MCP actions in phase 5. |
| `safety_and_validation.sensitive` | No. |
| `task_category_complexity`, `intent`, `constraints` | No. |
| Empty `output` from a phase 4 to 6 call | Silently skipped. |

## 6. What carries across messages

`SessionService` keeps, per session, the last `AI_AGENT_HISTORY_TURNS` (default 6) exchanges: the user text and the reply. Phases 1 and 2 see it. Nothing else survives: not the plan, not the outputs, not a pending confirmation. A paused flow is not resumed. The user's answer starts a new run from phase 1, with the question in the history.

## 7. Where each thing lives

| Thing | File |
|---|---|
| Order of steps, pause rule | `application/orchestration/pipeline.py` |
| Phase definitions (model, schema, input, apply) | `application/orchestration/phases/*.py` |
| Payload building, token metrics | `phase_runner.py`, `metrics.py` |
| Action tree walking (4, 5, 6) | `action_walker.py`, `action_tree.py` |
| Question for the user | `clarification.py` |
| Schemas | `schemas.py`, `schema/response/` |
| Prompts | `prompts/advanced/`, `application/system_prompts/general.py` |
| LLM JSON to domain | `infrastructure/outbound/llm/response_mapper.py` |
| MCP tools | `infrastructure/outbound/llm/tools.py`, `infrastructure/outbound/mcp/` |

## 8. Findings: prompts, schemas and code disagree

Each was checked in the code; A, B and D were also reproduced with a small script. None has been seen against a real LLM. Severity is about the effect on a real conversation.

| # | Severity | Finding |
|---|---|---|
| A | High | **The questions for the user are lost.** The schema field is `requested_user_input`. The prompts, the mapper and the domain use `request_user_input`. The schema forbids extra fields, so the model will write `requested_user_input`, and the mapper reads a name that is never there. Phase 99 then falls back to `blocking_reason` or `recommended_action` (or the fixed English text). Reproduced: the mapper returns `None` for an answer with `requested_user_input: ["what city?"]`. |
| B | High | **Subactions are dropped.** The schema and prompt call the nested list `subactions`. The mapper never reads it, and the domain field is `subtasks`. The planned tree becomes a flat list, so the "children first" logic of phases 4 to 6 never runs and prompt 2's hierarchical ids are decorative. Reproduced: `subtasks` is `None` after mapping an answer with a `subactions` entry. |
| C | High (unverified) | **`mcp_context.server_id` has `"enum": []`.** Every action must include `mcp_context`, and its `server_id` can only be a value of an empty enum, so no valid answer exists. Providers that validate the schema may reject the request at phase 2 (or accept and ignore it). The description says it should be filled with the real servers. Also, the mapper drops `mcp_context` unless `server_id`, `tool_name` and non-empty `parameters` are all present, so a tool with no arguments loses its context. |
| D | High | **Outputs do not flow between phases 4 and 5.** Phase 5 starts with an empty `completed_outputs`, and phase 4 runs all its actions before any MCP action. So an MCP action that depends on a cognitive action gets `dependency_outputs: {}`, and a cognitive action that depends on an MCP result runs before it exists. Reproduced: in the recorded run, the MCP action depends on `a1` and receives `{}`. |
| E | Medium | **`constraints` is never produced.** No phase writes it, so phases 7 and 8 always get `None`. Language, tone, length and format of the reply are not controlled. For a voice robot this matters (short, spoken, in the user's language). |
| F | Medium | **Triage cannot pause.** Prompt 1 tells it to ask when the request is ambiguous, but the pipeline does not check after phase 1, and phase 2 overwrites its `next_step`. |
| G | Medium | **Confirmation is not a real loop.** After `awaiting_confirmation`, the user's "yes" starts a new run from phase 1, and phase 3 will likely ask again. Also phase 99 gets `recommended_action` as if it were missing information. |
| H | Medium | **MCP failures are invisible.** Only `output` is read from phase 5. If the tool fails and the LLM writes `error`, it is ignored, `output` stays empty and phase 7 sees nothing. Phase 2 also sees the full server configs (URLs, Docker commands, local paths) but no tool names, so `tool_name` is a guess. Phase 5 in the end picks tools itself. |
| I | Medium | **Phase 8 can say "not done" and it is still spoken.** The reply is `expected_outcome` whatever `next_step` says. |
| J | Low | Inputs are Python `repr`, not JSON (section 2). It works but is noisy, and long `repr`s cost tokens. |
| K | Low | Temperature 1.0 for classification and JSON phases. Answers vary between runs. |
| L | Low | Phase 6 runs on every output, including cognitive ones that need no cleaning. One extra call each. |
| M | Low | `retry`, `error`, `complete` statuses, `retry_action_id`, `task_category_complexity`, `intent`, `mcp_routing` and `missing_information` exist in schemas or domain but nothing acts on them. |
| O | Low | The actions schema has `minItems: 1`, so even "hello" must be planned as at least one action. Together with phases 3 to 8 always running, small talk costs the full chain. |
| N | Low | Nothing validates `action_type` against the enum in the domain (any non-empty string is accepted), and a `clarification` action is executed by the worker instead of asking the user. |

## 9. Suggested order for working on the flow

Nothing here is done. Each item changes behavior, so each should get its own test and, where it changes an LLM call, a deliberate update of `tests/golden/flow_golden.json`.

1. **A and B (mapping).** Make the mapper read `requested_user_input` and `subactions` (or rename them in the schema, prompts and domain; pick one spelling). Pure code, no extra LLM cost.
2. **C (schema).** Fill `server_id` from the real MCP servers per request, or make the field a plain string. Then one real call to phase 2 to see the provider accept it.
3. **D (dependencies).** One shared `completed_outputs` for phases 4 and 5, and run the actions in dependency order instead of "all cognitive, then all MCP".
4. **H (MCP result).** Read `error`, keep it on the action, show phase 7 that a step failed. Give phase 2 the tool names.
5. **F, G (pauses).** Check after phase 1. Decide how a confirmation resumes (store the pending plan in the session).
6. **E (constraints).** Produce them in triage (language, tone, length, format) or set defaults for a voice reply.
7. **Cost and latency (L, K).** Skip phase 6 for cognitive outputs, lower temperature for phases 1 to 3, and consider a fast path when triage says no actions are needed.
8. **J.** Send JSON instead of `repr` (changes every prompt input, so do it last and re-record the golden file).

Open decision for you: the reply is currently plain text. If Brain should act on the decision (move an arm, choose a voice), the answer needs a structured field (for example an `actions_for_brain` list), and that changes the final phases and the API.
