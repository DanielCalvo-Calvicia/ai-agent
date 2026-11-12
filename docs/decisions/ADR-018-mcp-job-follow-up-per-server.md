# ADR-018 — The follow-up of an MCP job is code, chosen per server

**Status:** Accepted (2026-11-11, the maintainer's answers to [Q10](../setup/questionnaires/Q10_mcp-job-follow-up.md), recorded in [T-07.1](../tasks/T-07_mcp-job-follow-up/T-07.1_decisions.md); two changes to the first proposal: decision 3 is all or nothing, decision 8 offers the shipment tools). Epic [T-07](../tasks/T-07_mcp-job-follow-up/T-07_mcp-job-follow-up.md). **Built on 2026-11-11** (T-07.3 to T-07.7 and T-07.10: the interface, the loop, `dynamics_v1` and `dynamics_pending`, the operator prompt without job rules, the shipment tools; see "What was built" at the end); **not yet run against the real service** (T-07.9). It changes decision 3 of [ADR-011](ADR-011-mcp-streamable-http.md) (a `running` answer is followed up by the operator step) once it is accepted and built.

## Context

A tool call may answer before its query is done and hand back a job to read later. ADR-011 decided that the **operator step** (an LLM) follows that up once with `get_job_result`, and `prompts/5_mcp_operator.txt` says how: look for `status: running`, take its `job_id` and `next_offset`, call `get_job_result` once with `offset_rows`.

A call made on 2026-11-11 to `customer_orders` (`customer_no` CL-1001, `scope` open) on the `Dynamics-Development` server showed that the real answer does not have that shape:

- The first answer was `## open_orders (open)` and `note: pending: the query is still running as job <id> (running): read it with get_job_result`. There was no `status: running` line and no `next_offset`.
- The job answered with `returned`, `total`, `job_id`, `offset: 0` and the table; with the job done there is no `next_offset`.
- With `scope` all the answer is two tables, so each one can have its own job. The rule "once" does not cover that.
- A bad guess by the operator ends as a "pending" text taken as the result, and the writer tells the user that the query is still running when it may be done.

Two more facts shape the decision:

- **The MCP servers differ and not all can be changed.** Some are ours (`dynamics_microservice`), others will not be. A fix that depends on one server changing its answer does not hold for the others.
- It was not checked whether the shape seen on 2026-11-11 is a change of the Go service or a difference between that server and the one used in T-01.9. The fake server of `tests/test_mcp_dynamics_flow.py` and `tests/fixtures/dynamics_tools_snapshot.json` follow the older shape.

> **Note, 2026-11-11 (later the same day):** the call described above was made on `Dynamics-Development`, an **older** version of the service. The current one (`local-dynamics`) already has the contract this ADR asks for in decision 6 (`status: ok | running | error`, `job_id`, `retry_after_seconds`, a status per table; `docs/api/mcp.md` of the Go service), so `dynamics_v1` is that contract and `dynamics_pending` is the legacy shape, kept until the Go service drops its `note: pending: …` lines (not before 2027-01-11). The decisions below stand.

## Decision

1. **The follow-up is code, not a prompt.** The MCP adapter (`MCPToolExecutor`, `infrastructure/outbound/mcp/`) detects a job in the answer of a call, reads it with the server's read tool and gives the operator the final answer, or a plain "still running" when the budget ran out. The operator no longer follows jobs up and its prompt loses the `RUNNING ANSWERS` section.
2. **The protocol is declared per server.** Each `mcps/<server>.json` has a `job_protocol`:
   - `none` (the default): the server has no jobs and nothing is done. A new server cannot break.
   - A named protocol built in code, such as `dynamics_v1` (`status: running` with `job_id` and `next_offset`) and `dynamics_pending` (the `pending … job <id>` note).
   - `custom`, later and only when a real server needs it: a pattern for the id, the name of the read tool, the name of its offset parameter, and the signs of "done" and "still running".
3. **One interface, one adapter per protocol.** Four operations: `detect(answer)` returns a `job_id` and an optional offset, or nothing; `poll(job_id, offset)` reads it; `is_done(answer)`; `cancel(job_id)` when the server allows it. The generic part does what is common: short waits between tries, the shared budget of 60 s (`MAX_TOOL_WAIT_SECONDS`), `cancel_job` when the budget ends, and `offset_rows` only when there is an offset. **One job per table, all or nothing** (Q10-9): an answer that holds several jobs (`scope` all gives two tables) has every job followed; if one does not end in time the ones still running are cancelled, no table is given (a table that did end is discarded) and the reply says the query is still running.
4. **Only the declared read tool is called, only with the id the code found.** The text of an answer never decides which tool is called or with what (an answer is data, ADR-011 decision 7). This replaces the operator's exception to "call only the tool in `action.mcp_context.tool_name`".
5. **A shape the protocol does not know fails visibly.** One log line with the server name and the outcome, never the content (ADR-011 decision 6), and the user hears that the query could not be completed, not an empty result.
6. **For the servers we own**, the target shape is a header `status: ok | running | error`, a `job_id`, a `retry_after_seconds` and the same format for every table of an answer. It is a request to their maintainers, not a condition: the agent works with the shape each server has today. `MCP_JOB_WAIT` of `dynamics_microservice` must stay below `AI_AGENT_MCP_CALL_TIMEOUT_SECONDS` (30 s).
7. **Tests.** A fake server for each protocol, with the shapes seen on a real server, including a job that ends on the second read, a `scope` all answer with two jobs and a job that never ends (the budget and `cancel_job`). A snapshot of a real answer per protocol is refreshed by hand.
8. **In this change (Q10-11):** the tools `order_shipments`, `shipment_status` and `shipment_tracking` that the server lists today are offered: `allowed_tools`, the snapshot of the tool list, the planner rules, tests and documents (task T-07.10, after the real answers of the service are known). Until it is done they stay hidden.

## Order of work (planned)

1. The interface and the protocol `none`: no change in behaviour.
2. `dynamics_pending` and `dynamics_v1`, with their tests.
3. The operator prompt without its job rules; the golden regenerated on purpose after reading its diff.
4. The documents: `docs/api/api.md`, `docs/architecture/architecture.md`, `docs/rules/schemas-and-prompts.md`, `docs/configuration/environment-variables.md` (the `job_protocol` field) and the task board.
5. The shipment tools (T-07.10), once the answers of the service are known.
6. `custom`, only when a server needs it.

## Consequences

- Positive: a job is followed the same way whatever the model does; each server has its own shape without code outside its adapter; a server that cannot be changed is covered; the budget and the cancel are in one place and tested.
- Negative: all or nothing throws away a finished table when its sibling is slow; more code in the adapter; a change in a server's shape is not absorbed until its adapter changes (it fails visibly instead); one more field in the server file; a new ADR-011 note and a golden change.
- Open: whether the shape of 2026-11-11 is the final one of the Go service (to confirm with its maintainer), and the short wait between tries (a constant, to measure on a real run).

## Alternatives not taken

- **Only a better prompt** (accept both shapes, `offset_rows` only when there is a `next_offset`): the cheapest, and it stays as the fallback if this ADR is not built, but it keeps depending on the model reading free text, and it does not cover two jobs in one answer.
- **Only change the server**: it does not help the servers that cannot be changed.
- **A follow-up as a second planned action**: ruled out in ADR-011 and for the same reasons.
- **One regular expression for every server**: it breaks with the first server that has another shape and hides which one it was.

## What was built (2026-11-11)

- `infrastructure/outbound/mcp/`: `job_protocol.py` (interface, `none`, registry, check of a server file's job settings), `job_follow_up.py` (the loop), `job_protocols/` (`dynamics_v1`, `dynamics_pending`) and the hook in `tool_executor.py`. The interface grew from the first proposal: `state` (done, running or unknown) replaced `is_done`, and `merge` was added. A job whose id cannot be read is detected as an empty id and fails as an unknown shape.
- New outcomes `job_done`, `job_running`, `job_cancelled`, `job_unknown_shape` in `TOOL_OUTCOMES`; one warning, `MCP job answer not understood`, with the server name and the protocol only.
- **`dynamics_v1` is the jobs contract of `dynamics_microservice` since 2026-11-11** (decision 6 asked for it and the Go service delivered it: `status: ok | running | error`, `job_id`, `retry_after_seconds`, a status per table). `dynamics_pending`, the shape first seen on an older server, is legacy: the Go service keeps its `note: pending: …` lines until at least 2027-01-11 and says ai-agent moves to `dynamics_v1` before then. `mcps/dynamics_microservice.json` declares `dynamics_v1`.
- The operator prompt has no job rules (golden changed on purpose: only the phase 5 prompt). The shipment tools (decision 8) are offered: allowed tools, planner and writer rules, `capabilities.txt` (shared, so the golden changed in 76 calls: only the prompt length and hash).
- **`job_recall_tools` (T-07.11)**, found after the Dynamics session answered (T-07.2): a composed tool (the three shipment tools) that becomes a job names only an inner query; reading it gives the wrong rows, so the server file lists such tools and they are called again with the same arguments after 3 s. It refines decision 4: still no tool outside the server file's lists, and never one an answer names.
- Not built: `custom` (decision 2), reading the pages after the first of a result (`complete: no`), a spoken "one moment" (Q10-7). Tests: 1493 pass; scripted servers and the Go service's own contract snapshots as fixtures.
- **First real run (T-07.9, 2026-11-11):** four messages on `dynamics` with real models against the current local service: orders and the two shipment tools answered right, all calls `ok` in under 1 s, so **no job occurred and the follow-up was not exercised against the real service**. The `.env` URL points at an older service (no shipment tools, no `status` line): `dynamics_v1` needs the new service before or with the agent (against the old one a pending answer would not be detected; the writer would say it is still being worked on).
- Open: a run that makes a job happen; a call of two chained slow steps can take 50 s while the per-call limit is 30 s (T-07.2 open point); the shipment tools were not run by the Go service against the real sandbox.

## Note, 2026-11-12: the files moved

The code of this ADR is the same; its files are now `infrastructure/outbound/mcp/jobs/`: `protocol.py` (was `job_protocol.py`: the interface and `none`), `registry.py` (the protocols by name; was in `job_protocol.py`), `settings.py` (the check of a server file's job settings; was in `job_protocol.py`), `follow_up.py` (was `job_follow_up.py`) and `protocols/` (was `job_protocols/`). The protocols no longer register themselves: `registry.py` lists them, so the lazy import that `job_protocol.py` needed is gone. The text above says where each thing was when it was built.

The same day the rest of `outbound/mcp/` was grouped by usage (`config/`, `connection/`, `catalog/`, `execution/`; only `server.py` stays at the root); `tool_executor.py`, where the hook of this ADR lives, is `execution/tool_executor.py`.
