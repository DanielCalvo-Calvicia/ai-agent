# Answers that carry a job, per protocol

One file per kind of answer of the job protocols of `infrastructure/outbound/mcp/job_protocols/` (T-07.7, ADR-018). Placeholder data
only: no real customer, order or job id. `tests/test_mcp_job_protocols.py` checks that each protocol reads its files, and the fake
server of `tests/test_mcp_dynamics_flow.py` serves them.

| File | Provenance |
|---|---|
| `dynamics_pending/first_one_table.txt` | the shape of the real call of 2026-11-11 (`customer_orders`, scope `open`: a `pending` note and a job id), with placeholder data |
| `dynamics_pending/first_two_tables.txt` | **assumed**: the same note once per table, as `scope` all would give; never seen (T-07.2, question 3) |
| `dynamics_pending/read_done_open.txt`, `read_done_archived.txt` | the shape of the job result seen on 2026-11-11 (`returned`, `total`, `job_id`, `offset`, a blank line, the table) |
| `dynamics_pending/read_running.txt` | **assumed**: the answer of the read tool while the job still runs was never seen (T-07.2, question 2) |
| `dynamics_v1/first_running.txt` | the shape of the documents of `dynamics_microservice` (`status: running`, `job_id`, `next_offset`), tasks README fact F4 |
| `dynamics_v1/read_done.txt` | the job result, as above |
| `dynamics_v1/read_running.txt` | **assumed**, as `dynamics_pending/read_running.txt` |

When the service answers T-07.2, replace the assumed files with real examples (placeholders for the data) and say so here.
