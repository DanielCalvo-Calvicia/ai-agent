# ADR-019 — A fast tool path as a common module; profiles choose its MCP servers and steps

**Status:** Proposed (2026-11-11, branch `feature_fast_profile`). The maintainer confirmed the understanding below on 2026-11-11; the eight decisions at the end are still to be answered (T-08.1). **Nothing in this ADR is built.**

## What was understood (confirmed by the maintainer)

1. A simple data request, such as "How are my orders? I'm CL-1001", has to answer in **20 s at most**. Today it takes 37 to 46 s.
2. There is **no Dynamics-specific path**. A **common module** handles "a request that needs at most one read-only tool call" and knows no MCP server by name.
3. **The profile decides** which MCP servers it uses (its `tools`) and which steps run (its flow and its step overrides). A profile for another server, or for another set of steps, is a JSON file, not code.
4. `special` and `dynamics` stay as they are, for requests that need a real plan.

## Context

- **Measured on 2026-11-11** (`dynamics` profile, `claude_mixed`, the current local service, two runs): 8 sequential model calls, about 49,000 tokens, the tool call 0.6 to 1.8 s.

  | Step | Tokens out | What it really does |
  |---|---|---|
  | `mcp_operator` | 917 | Rewrites the table the tool returned |
  | `data_engineer` | 780 | Copies the same table again |
  | `cognitive_worker` | 396 | An extra action nobody asked for |
  | `project_manager` | 390 | The plan (11,570 tokens in) |
  | `editor_in_chief` | 279 | Final polish |
  | `draft_writer` | 228 | The reply |
  | `triage_specialist` | 124 | Classify |
  | `safety_quality_gatekeeper` | 63 | Always "no confirmation" for reads |

  Latency follows the tokens a call **writes**, so the three copying steps are the cost. The time per step is **not measured**: the log of an LLM call has no duration (see decision 10 and T-08.2).
- [ADR-015](ADR-015-profiles-flows-steps.md) gives the layers: a profile names a flow, its tools, its models and its prompt appends; a flow is a JSON list of steps; a step is a JSON declaration or a code step. [ADR-016](ADR-016-runtime-folder-layout.md) gives the folders.
- [ADR-018](ADR-018-mcp-job-follow-up-per-server.md) already makes the MCP adapter follow jobs in code, so the new module must not do that again.
- The client chains profiles: it asks `identification` first. A profile can **require** that classification as `inputs`, as `chat` does, so a fast flow needs no triage of its own.
- **Two limits today.** `ToolDefinition` has no read-only information. A profile's inline `steps` are accepted by the check but the runner refuses to run them (`needs steps as files`).

## Decision

1. **A new flow `fast`** (`flows/fast.json`) with three steps, in a step group `fast`:
   - `tool_selector` (LLM, one call) chooses the tool call, asks for a missing input, or says no tool fits.
   - `tool_caller` (**code**) calls the tool through the adapter. Jobs are already handled there (ADR-018).
   - `answer_writer` (LLM, one call) is the draft writer and the editor in one.
2. **The module knows no server.** Nothing in `runtime/step/library/fast/` or in `support/tools/direct_call.py` names a server or a tool, and a test enforces it. What one MCP means (how to pick its tools, how to read its answers) lives in the profile's prompt appends under `prompts/profiles/`, as `dynamics` does today.
3. **The profile switches MCP servers and steps.** `profiles/dynamics_fast.json` carries `flow: fast`, `models`, `tools.servers`, `overrides.<step>.prompt_append` and `inputs.requires: [user_goal, task_category]`. A profile for another server is the same file with other `tools` and other appends. A different set of steps is another flow file (for example `flows/fast_checked.json` with a gate) chosen by `flow`. A different model or prompt for one step is an override. None of these needs code.
4. **`tool_selector` contract.** It reads `message`, `history`, `answers`, `user_goal`, `task_category` and the tools its scope offers. It writes **one** action (`mcp_tool_call` with a complete `mcp_context`), or `required_inputs` for a missing value (the pause and resume of the special flow are reused as they are), or one `generation` action when no tool fits. It reuses the existing `actions` and `next_step` schema pieces, so there is no new schema and no new `domain/` object. Its prompt is short; the tool descriptions are its main input.
5. **`tool_caller` contract.** It calls the action's tool with its parameters through the new port method `call_tool`, inside the tool scope of the step. The result goes to `action.output` untouched; a tool error goes to `action.error`. Each call is still recorded (`record_tool_call`). No model rewrites the answer: it already follows the contract.
6. **`answer_writer` contract.** It reads `message`, `user_goal`, `task_category` and `actions`. It writes the reply (`user_goal.expected_outcome`, as the editor does) and `next_step`. The rules of language, plain text, one honest sentence per error and `Pendiente` stay in the profile's appended prompt, so they are not Dynamics rules in the common prompt.
7. **One shared direct-call helper**, `support/tools/direct_call.py`, used by `tool_caller` **and** by `ActionExecutor` for any independent MCP action (no dependencies, no subactions, a complete `mcp_context`). The LLM operator stays only as the fallback for dependent actions, and the data engineer only for an answer without the contract shape. This also shortens `special` and `dynamics`.
8. **Read-only only.** The fast path runs a tool only if the profile's scope allows it **and** the tool is read-only. `ToolDefinition` gets a `read_only` flag from the MCP `readOnlyHint` annotation, which the Dynamics tools already set. A tool without the hint is refused. **The check is at run time**: `assemble()` works from files only (T-05.6) and the annotation is on the live server, so the selector is shown only the read-only tools of its scope and the caller refuses any other one (T-08.4; corrected on 2026-11-11 when the tasks were written).
9. **Not in scope:** more than one tool call, actions that depend on each other, tools that need confirmation, a gate step, and a router inside the service (ADR-015 forbids it). A request that needs more is for `dynamics`, chosen by the client.
10. **Target and measure.** The median of 5 real runs of the simple message is **20 s or less**. The estimate is **8 to 14 s** (two model calls of 4 to 6 s and a tool of 1 to 2 s); it is **not measured**. `duration_ms` is added to the record and the log line of an LLM call first (T-08.2), so every later change is judged in seconds.

## What changes

| Today | After |
|---|---|
| A simple read = 8 model calls | 2 model calls and one code step |
| The operator and the data engineer copy the tool table | The tool answer goes through as it is |
| A profile can only reuse a full-plan flow | A profile can use `fast`, or any other flow file |
| `ToolDefinition` has no read-only flag | `read_only`, from `readOnlyHint` |
| An LLM call has no duration in the log | `duration_ms` in the record and the log line |

## Files

**New:** `flows/fast.json`; `step_defs/{tool_selector,tool_caller,answer_writer}.json`; `prompts/50_tool_selector.txt` and `prompts/51_answer_writer.txt`; `runtime/step/library/fast/tool_caller.py`; `support/tools/direct_call.py`; `profiles/dynamics_fast.json` (with a real token hash); a model set for the profile (name to decide); this ADR; the epic folder `docs/tasks/T-08_fast-tool-path/`.

**Changed:** `application/outbound/ports/mcp_ports.py` (`call_tool`; `ScopedTools` forwards it with its scope); `infrastructure/outbound/mcp/tool_executor.py` and `tool_catalog.py`; `domain/value_objects/llm_request/tool.py` (`read_only`); `runtime/step/library/special/action_executor.py`; `runtime/step/build.py` and `functions.py` (the builders and the input function of the new steps); `support/metrics.py` and `runtime/step/runner.py` (`duration_ms`).

**Tests and generated files:** new tests for the direct call, the three steps, the read-only check, the "no server name in the module" check and the assembly of the new profile. The golden file changes **on purpose**: a new profile block, and the scenarios that run an MCP action lose their `phase5` and `phase6` calls. `docs/models/profiles.md` is regenerated.

**Documents:** `architecture.md`, `schemas-and-prompts.md`, `monitoring.md`, `requirements.md` (a latency requirement, marked planned), `profiles/README.md`, `CLAUDE.md` and the task board.

## Consequences

- **Positive:** a second MCP server needs only a profile file and a prompt append. The path is deterministic and measured. `special` and `dynamics` get faster too.
- **Negative:** there are two ways to answer a data request, so two sets of prompts to keep right. A fast selector on a cheap model can pick the wrong tool; the fixed messages are the judge. A request that needs two tools is not for this profile. The client must chain `identification` first.
- **Risk:** the selector's input is mostly the tool descriptions, so a server with many tools makes it slower and less exact.

## Alternatives not taken

- **A flow written only for Dynamics.** Rejected by the maintainer.
- **Only trimming `special`.** Removing the operator, engineer and worker copies reaches about 18 s but leaves no margin. Its useful part is kept (decision 7).
- **One model call that uses the tools itself** (one agentic step doing selector, caller and writer). Fewer files, but it gives up the tool allow-list check, the read-only check and the per-step metrics. Revisit if two calls are still too slow.
- **Making the profile's inline `steps` runnable.** It would let a profile list steps without a flow file, but it needs work in the flow loader. One flow file per variation works today.

## Plan of work (epic T-08, not created yet)

1. **T-08.1** Decisions (the questions below).
2. **T-08.2** `duration_ms`, so the before and after are measured.
3. **T-08.3** `call_tool` and `direct_call`, used by `ActionExecutor`. Measure `dynamics` before and after.
4. **T-08.4** The `read_only` flag from the annotation, and its check.
5. **T-08.5** The three steps, the flow, the prompts and `dynamics_fast`.
6. **T-08.6** Tests and the golden file.
7. **T-08.7** Tuning on the real models, one change at a time (the T-06 rule).
8. **T-08.8** Documents.
9. **T-08.9** Real run of the fixed messages for `dynamics_fast`, compared with `dynamics`.

## Decisions still to answer (the default first)

1. **Names:** profile `dynamics_fast`, flow `fast`.
2. **Triage inside the fast flow:** no. The profile requires the `identification` result as `inputs`. Alternative: add the cheap triage (about 3 s) for clients that cannot chain.
3. **Read-only check:** by the `readOnlyHint` annotation. Alternative: the profile's tool list alone.
4. **A request that needs more than one tool:** the reply says so plainly and the client picks `dynamics`. A structured signal in `output` can come later.
5. **Different steps per profile:** one flow file per variation. Alternative: make inline `steps` runnable.
6. **Models:** Haiku on the selector and the writer, Sonnet only if quality fails.
7. **Also use the direct call in `special` and `dynamics`:** yes.
8. **Branch:** `feature_fast_profile`, with commits only when the maintainer asks.

## Acceptance

- The median of 5 real runs of the simple message is 20 s or less.
- The fixed messages for the profile are answered right when the maintainer reads them.
- No server name appears in the module, and `check_agent.py` passes.
- `dynamics` and `special` are no worse on their fixed messages.
- The documents are true.
