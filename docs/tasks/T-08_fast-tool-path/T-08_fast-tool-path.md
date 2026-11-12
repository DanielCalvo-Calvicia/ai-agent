# T-08 — A fast tool path as a common module; profiles choose its MCP servers and steps

| | |
|---|---|
| Status | in-progress (planned 2026-11-11; T-08.1 done the same day, [ADR-019](../../decisions/ADR-019-fast-tool-path.md) accepted; nothing built) |
| Kind | epic |
| Parent | project |
| Depends on | T-07 (the MCP adapter that follows the jobs) |
| Blocks | — |

> Source: the real timing of 2026-11-11: a simple request ("How are my orders? I'm CL-1001") takes 37 to 46 s on the `dynamics` profile (8 sequential model calls, about 49,000 tokens; the operator and the data engineer copy the tool table, the planner adds an extra action). The maintainer wants it at **20 s or less**, **without a path written for one MCP server**: a common module, and profiles that choose the MCP servers and the steps. Plan and reasons: [ADR-019](../../decisions/ADR-019-fast-tool-path.md) (proposed).

## Goal

A request that needs at most one read-only tool call is answered by a flow of three steps (a tool selector, a tool caller in code, an answer writer) that knows no MCP server by name. A profile file names the servers (`tools`), the flow and the step overrides: another server or another set of steps is a JSON file, not code. The median of 5 real runs of the simple message is **20 s or less**.

## What exists and what changes

| Today | After T-08 |
|---|---|
| A simple read = 8 model calls (triage, planner, gate, operator, data engineer, cognitive worker, writer, editor) | 2 model calls (selector, writer) and one code step (the caller) |
| The operator and the data engineer copy the tool table (917 and 780 output tokens) | The tool answer goes through as it is; the LLM operator and engineer are only a fallback |
| An LLM call has no duration in the log | `duration_ms` in the record and the log line |
| `ToolDefinition` has no read-only information | `read_only`, from the MCP `readOnlyHint` |
| A profile can only reuse a flow file; its own `steps` are refused by the runner | A profile can use `fast`, any other flow file, or list its own steps (T-08.10) |

## Subtasks

| Order | Task | Kind | Status |
|---|---|---|---|
| 1 | [T-08.1 Decisions](T-08.1_decisions.md) | decision | done (2026-11-11) |
| 2 | [T-08.2 `duration_ms` in the LLM call record](T-08.2_duration-ms.md) | code | done (2026-11-11) |
| 3 | [T-08.3 The direct tool call and the executor](T-08.3_direct-tool-call.md) | code | done (2026-11-11), 39 s to 23 s measured |
| 4 | [T-08.4 Read-only tools](T-08.4_read-only-tools.md) | code | done (2026-11-11) |
| 5 | [T-08.10 A profile's own steps run](T-08.10_profile-own-steps.md) | code | done (2026-11-11) |
| 6 | [T-08.5 The fast flow, its steps and the profile](T-08.5_fast-flow-and-profile.md) | code | done |
| 7 | [T-08.11 The profile with the triage](T-08.11_triage-profile.md) | code | done |
| 8 | [T-08.6 Tests and the golden file](T-08.6_tests-and-golden.md) | test | done |
| 9 | [T-08.7 Tuning on the real models](T-08.7_tuning-on-real-models.md) | manual | done |
| 10 | [T-08.8 Documentation](T-08.8_documentation.md) | docs | done |
| 11 | [T-08.9 First real run of the profile](T-08.9_first-real-run.md) | manual | done |

## Exit criteria

The median of 5 real runs of the simple message on the fast profile is 20 s or less; the fixed messages for the profile are answered right when the maintainer reads them; no server name appears in the module (a test); `check_agent.py` passes with the new profile; `dynamics` and `special` are no worse on their fixed messages; the two profiles (`dynamics_fast` and `dynamics_fast_triage`) assemble and answer; the documents are true.

## Rules that bind every task of this epic

- **The common module knows no server.** Nothing in `runtime/step/library/fast/`, `support/tools/direct_call.py`, `flows/fast.json`, the three step declarations or the two generic prompts names a server or a tool. What one MCP means goes in the profile's prompt appends.
- Dependencies go one way (ADR-016): a step uses the port, not the infrastructure.
- No log line, metric or span holds a tool argument or a tool answer (name, outcome, duration, tries only).
- The fast path runs read-only tools only (T-08.4).
- Every change to a prompt, schema, model or message format changes the golden file: read the diff first, then regenerate on purpose.
- **No real call to a model or to the real service without asking** (T-08.3 measures, T-08.7 tunes and T-08.9 runs: each asks first). Commit and push only when asked.
- A change that is worse on the real models is reverted, not tuned in place (the T-06 rule): one change at a time, a report before and after.
- The baseline of the [tasks README](../README.md) section 3.

## Open points

- **Which client uses the fast profiles today** was not said (Q11-4): the client is one thing and uses one profile. Brain sends no profile yet, so until it chains `identification`, the profile that works for it is `dynamics_fast_triage`.
- Whether two model calls are enough for 20 s: the estimate (8 to 14 s) is **not measured**; T-08.2 gives the seconds.
- Reading more than the first page of a result, and a request that needs two tools, stay out of scope.
