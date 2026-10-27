# Task order

The order in which the tasks must be done, with the state of each one and the date its file was last updated. It follows the execution protocol of the [tasks README](README.md) (section 2): the first task that is `todo` and whose dependencies are `done`.

**Keep this file true:** every change to a task (a status, a dependency, a new task, an order change) updates this table, the board of the [tasks README](README.md) section 5 and the task file itself.

## States

| State | Meaning |
|---|---|
| Done | Implemented and verified (or, for a decision, taken and recorded) |
| In progress | Some of its subtasks are done and some are not |
| Todo | Ready to start when its dependencies are done |
| Awaiting user | A decision needs an answer; it stops the chain |
| Blocked | Waits for another task or for a decision |

Written on 2026-10-27.

## A. T-01 Use the dynamics_microservice MCP tools

| # | Task | Name | Kind | State | Detail | Depends on | Last updated |
|---|---|---|---|---|---|---|---|
| 1 | [T-01](T-01_dynamics-mcp/T-01_dynamics-mcp.md) | Use the dynamics_microservice MCP tools (epic) | epic | Todo | nothing built | — | 2026-10-27 |
| 2 | [T-01.1](T-01_dynamics-mcp/T-01.1_decisions.md) | Decisions | decision | Done | decided in Q01 and Q02 (2026-10-27) | — | 2026-10-27 |
| 3 | [T-01.2](T-01_dynamics-mcp/T-01.2_streamable-http-transport.md) | Streamable HTTP transport in the MCP client | code | Todo | can start now | — | 2026-10-27 |
| 4 | [T-01.4](T-01_dynamics-mcp/T-01.4_mcp-timeouts.md) | Timeouts and retries that fit a slow query | code | Todo | can start after T-01.2 | T-01.2 | 2026-10-27 |
| 5 | [T-01.3](T-01_dynamics-mcp/T-01.3_server-config-and-settings.md) | Server config and settings | code | Todo | after T-01.2 | T-01.2 | 2026-10-27 |
| 6 | [T-01.10](T-01_dynamics-mcp/T-01.10_server-availability.md) | Server availability: hide, cache, check, log | code | Todo | after T-01.3 | T-01.2, T-01.3 | 2026-10-27 |
| 7 | [T-01.11](T-01_dynamics-mcp/T-01.11_tool-call-cap.md) | Cap of MCP tool calls per message | code | Todo | after T-01.2 | T-01.2 | 2026-10-27 |
| 8 | [T-01.12](T-01_dynamics-mcp/T-01.12_tool-call-metrics.md) | Tool call metrics | code | Todo | after T-01.2 and T-01.4 | T-01.2, T-01.4 | 2026-10-27 |
| 9 | [T-01.5](T-01_dynamics-mcp/T-01.5_capabilities-and-triage-prompts.md) | Tell the agent it has Business Central data | code | Todo | after T-01.3 | T-01.3 | 2026-10-27 |
| 10 | [T-01.6](T-01_dynamics-mcp/T-01.6_planner-guidance-and-jobs.md) | Planner: guidance, jobs and answers | code | Todo | after T-01.5, T-01.10 and T-01.11 | T-01.5, T-01.10, T-01.11 | 2026-10-27 |
| 11 | [T-01.7](T-01_dynamics-mcp/T-01.7_verification.md) | Verification with scripted LLMs | test | Blocked | | T-01.2 to T-01.6, T-01.10 to T-01.12 | 2026-10-27 |
| 12 | [T-01.8](T-01_dynamics-mcp/T-01.8_documentation.md) | Documentation and ADR | docs | Blocked | | T-01.2 to T-01.6, T-01.10 to T-01.12 | 2026-10-27 |
| 13 | [T-01.9](T-01_dynamics-mcp/T-01.9_first-real-run.md) | First real run | manual | Blocked | costs money; the maintainer runs it and closes the epic | T-01.7, T-01.8 | 2026-10-27 |
