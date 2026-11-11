# T-07 — The follow-up of an MCP job is code, chosen per server

| | |
|---|---|
| Status | in-progress (planned 2026-11-11; T-07.1 done the same day, [ADR-018](../../decisions/ADR-018-mcp-job-follow-up-per-server.md) accepted) |
| Kind | epic |
| Parent | project |
| Depends on | T-01 (the MCP tools) |
| Blocks | — |

> Source: a real call of 2026-11-11 to `customer_orders` on the `Dynamics-Development` server answered `note: pending: the query is still running as job <id> …`, not `status: running` with `next_offset`, which is what `prompts/5_mcp_operator.txt`, the fake server of the tests and the documents assume. Plan and reasons: [ADR-018](../../decisions/ADR-018-mcp-job-follow-up-per-server.md) (proposed).

## Goal

A tool answer that carries a job is followed up to its result by the MCP adapter, with the protocol each server file declares, inside the 60 s of the message. The operator step never reads a job any more. A server whose shape is not known fails visibly, never as an empty result.

## What exists and what changes

| Today | After T-07 |
|---|---|
| The operator step (an LLM) follows a `status: running` answer once with `get_job_result`; its prompt names `status: running`, `job_id` and `next_offset` | `MCPToolExecutor` detects the job, polls it, and gives the operator the final answer (or "still running" when the budget ends) |
| One shape is assumed for every server | `job_protocol` in each `mcps/<server>.json`: `none` (default), `dynamics_v1`, `dynamics_pending`; `custom` is not built |
| One follow-up per answer; `scope` all has two tables | One job per table, all or nothing: if one does not end in time the running ones are cancelled and no table is given |
| The shipment tools the service lists are hidden | Offered to the planner (T-07.10) |
| A "pending" answer the operator does not follow ends as a result | Unknown shape: a log line with the server name and the outcome, and the user is told the query could not be completed |

## Subtasks

| Order | Task | Kind | Status |
|---|---|---|---|
| 1 | [T-07.1 Decisions](T-07.1_decisions.md) | decision | done (2026-11-11) |
| 2 | [T-07.2 Ask the Dynamics service for its contract](T-07.2_dynamics-contract.md) | manual | in-progress (sent 2026-11-11 to the Dynamics session; waiting for the answer) |
| 3 | [T-07.3 The protocol interface, `none` and the `job_protocol` field](T-07.3_protocol-interface.md) | code | done (2026-11-11) |
| 4 | [T-07.4 The follow-up engine](T-07.4_follow-up-engine.md) | code | done (2026-11-11) |
| 5 | [T-07.5 The protocols `dynamics_pending` and `dynamics_v1`](T-07.5_dynamics-protocols.md) | code | done (2026-11-11) |
| 6 | [T-07.6 The operator prompt without job rules](T-07.6_operator-prompt.md) | code | done (2026-11-11) |
| 7 | [T-07.7 Tests with a fake server per protocol](T-07.7_tests.md) | test | done (2026-11-11) |
| 8 | [T-07.10 Offer the shipment tools](T-07.10_shipment-tools.md) | code | done (2026-11-11) |
| 9 | [T-07.8 Documentation](T-07.8_documentation.md) | docs | done (2026-11-11) |
| 10 | [T-07.9 First real run](T-07.9_first-real-run.md) | manual | blocked (T-07.8) |

## Exit criteria

A job of each declared protocol is followed to its result, an answer with several jobs gives all its tables or none; the shipment tools are offered and answered; a job that does not end is cancelled and the reply says so; the operator prompt has no job rule; an unknown shape fails visibly; no log line, metric or span holds a tool argument or a tool answer; the suite passes with the golden file changed on purpose; the documents are true; one real run on `dynamics_microservice` passes.

## Rules that bind every task of this epic

- Dependencies go one way: the protocols and the engine are in `infrastructure/outbound/mcp/`; the budget (`tool_wait_budget`, `MAX_TOOL_WAIT_SECONDS`) stays where it is and is only read.
- Only the read tool the server file declares is called, only with the id the code found. The text of an answer never picks a tool or a parameter.
- No log line, metric or span holds a tool argument or a tool answer (name, outcome, duration, tries only).
- `dynamics_microservice` is read-only for this plan: never modify it. The change it needs is asked for in T-07.2.
- No real call to a model or to the real service without asking (T-07.9). Commit and push only when asked.
- The baseline of the [tasks README](../README.md) section 3.

## Open points

- Whether the `pending` shape is final in the Go service, or only on `Dynamics-Development` (T-07.2). **Settled on 2026-11-11:** `Dynamics-Development` is an older version; `local-dynamics` has the jobs contract (`status: ok | running | error`, `job_id`, `retry_after_seconds`, a status per table), documented in the Go service and read into `dynamics_v1` (T-07.5), which the server file declares. `dynamics_pending` is the legacy shape, until at least 2027-01-11.
- The short wait between two reads of a job: a constant, measured in T-07.9.
- `custom` (a pattern for the id, the read tool, the offset parameter, the signs of "done" and "still running") is **not scheduled**: it is built when a server needs it.
- The tools `order_shipments`, `shipment_status` and `shipment_tracking` are in this epic since Q10-11 (T-07.10). Open: their parameters and answers (T-07.2), and whether a shipment answer can carry a job.
- The branch: `feature_mcp_job_follow_up` from `feature` (Q10-13); not created yet.
