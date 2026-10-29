# T-01 — Use the dynamics_microservice MCP tools from ai-agent

| | |
|---|---|
| Status | in-progress (created 2026-10-27; T-01.1 to T-01.8 and T-01.10 to T-01.12 done on 2026-10-28; only T-01.9, the maintainer's first real run, is open) |
| Kind | epic |
| Parent | project |
| Depends on | the four-flow redesign and the docs layout (both merged into `feature`) |
| Blocks | — |

> Branch `feature_dynamics_mcp`. Source: the reading of `D:\Snowfactory\Programas\GO\dynamics_microservice` (`docs/api/mcp.md`, ADR-025) on 2026-10-27.

## Goal

The special flow can answer questions about Business Central (the orders of a customer, the state of an order, a customer card) by calling the MCP endpoint of `dynamics_microservice`, read-only. The Go service is not changed.

## What exists and what changes

| Today | After T-01 |
|---|---|
| The MCP client only speaks SSE (F6) | It also speaks Streamable HTTP, chosen by `type` in `mcps/<server>.json` |
| One 10 s limit for listing and calling (F7) | A configurable limit for calling, longer than the server's 20 s wait (F4) |
| `capabilities.txt` and triage say no external service exists (F9) | They say read-only Business Central data is available through tools |
| The planner sees tool names, descriptions and parameters | It also handles a `running` answer (the operator step follows up once with `get_job_result`, 60 s in total) and a tool error |
| Any tool a server lists is offered | Only the tools of the server file's `allowed_tools` are offered |
| A down server is still shown to the planner | It is hidden for the message, and the reply says it is not reachable |
| No cap on MCP actions per message | `AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE` (default 5, `0` = no limit) |
| Tool calls are invisible in the metrics | Name, outcome and duration in the logs, `SessionMetrics` and Langfuse, never a value |
| Each new tool server needs code | Each new Streamable HTTP server is one JSON file in `mcps/` |

## Subtasks

| Order | Task | Kind | Status |
|---|---|---|---|
| 1 | [T-01.1 Decisions](T-01.1_decisions.md) | decision | done (2026-10-27) |
| 2 | [T-01.2 Streamable HTTP transport](T-01.2_streamable-http-transport.md) | code | done (2026-10-28) |
| 3 | [T-01.4 Timeouts and retries](T-01.4_mcp-timeouts.md) | code | done (2026-10-28) |
| 4 | [T-01.3 Server config and settings](T-01.3_server-config-and-settings.md) | code | done (2026-10-28) |
| 5 | [T-01.10 Server availability](T-01.10_server-availability.md) | code | done (2026-10-28) |
| 6 | [T-01.11 Cap of tool calls](T-01.11_tool-call-cap.md) | code | done (2026-10-28) |
| 7 | [T-01.12 Tool call metrics](T-01.12_tool-call-metrics.md) | code | done (2026-10-28) |
| 8 | [T-01.5 Capabilities and triage prompts](T-01.5_capabilities-and-triage-prompts.md) | code | done (2026-10-28) |
| 9 | [T-01.6 Planner: guidance, jobs and answers](T-01.6_planner-guidance-and-jobs.md) | code | done (2026-10-28) |
| 10 | [T-01.7 Verification](T-01.7_verification.md) | test | done (2026-10-28) |
| 11 | [T-01.8 Documentation and ADR](T-01.8_documentation.md) | docs | done (2026-10-28) |
| 12 | [T-01.9 First real run](T-01.9_first-real-run.md) | manual | todo; the maintainer runs it and closes the epic |

## Exit criteria

With `DYNAMICS_MCP_URL` set, a request for the orders of a customer is routed to the special flow, planned as a call to a Dynamics tool, executed over Streamable HTTP, and answered in plain text, in the language of the user, with the data the user asked for (ai-agent sets no row limit); a `running` answer is followed up once, within 60 s in total; a tool error gets a short honest sentence; a server that is down is hidden and the reply says it is not reachable; more than `AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE` calls are not run and the reply says so; a tool offered by the server but not in `allowed_tools` is never offered to the planner; no log, metric or span holds an argument or an answer; the SSE servers still work; the whole suite passes; every document of the table in `CLAUDE.md` is true; the maintainer has run T-01.9 and closed the epic.

## Rules that bind every task of this epic

- Dependencies go one way: the transport lives in `infrastructure/outbound/mcp/`; `application/` only sees `McpToolsPort`.
- Business Central is read-only and the Go project is read-only for this plan.
- No real host, tenant, environment, company or customer code in git: `${DYNAMICS_MCP_URL}` and placeholders only.
- Nothing calls a real LLM or the real service except T-01.9, which **the maintainer runs** (the assistant prepares the command).
- Never log, measure or trace a tool argument or a tool answer (Q02-7).
- Everything is done on the one branch `feature_dynamics_mcp` (Q04-5); commit and push only when asked.
- No authentication is added in either service (Q01-9 A).
- The baseline of the [tasks README](../README.md) section 3.

## Open points

- Decided (T-01.1, 2026-10-27, Q01 to Q04): everything on the one branch `feature_dynamics_mcp`; workflows only, a trusted Langfuse with the data visible in the prototype, a public IP and port over plain HTTP set by environment, the Go service's default environment and company, Claude (one Sonnet model for every step), one pull request per task starting with T-01.2.
- Known limits, accepted for the prototype: no authentication in either service (a Cognito identity service is planned; who may see which customer is decided above ai-agent), no masking of data sent to Langfuse, no row limit in ai-agent, the enterprise data policy is `UNKNOWN`.
- The mixture of robot and generic client needs refinement later (a new epic).
- Unknown until T-01.9: the caller's timeout and the enterprise data policy.
- stdio servers stay unsupported; the project manager is still told they exist (known gap).
