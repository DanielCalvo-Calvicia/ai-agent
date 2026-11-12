# Answers that carry a job, per protocol

One file per kind of answer of the job protocols of `infrastructure/outbound/mcp/jobs/protocols/` (T-07.7, ADR-018). Placeholder data
only: no real customer, order or job id. `tests/test_mcp_job_protocols.py` checks that each protocol reads its files, and the fake
server of `tests/test_mcp_dynamics_flow.py` serves them.

## `dynamics_v1`: the jobs contract of `dynamics_microservice` since 2026-11-11

Copied from the contract snapshots of the Go service (`internal/tests/fixtures/infrastructure/inbound/mcp/contract/answers/`, its
`docs/api/mcp.md` section "The status lines and the jobs contract"), which are placeholders already: `ok`, `running`,
`finished_job_first_page`, `finished_job_last_page`, `job_not_found`, `two_tables_one_job`. **Refresh them by copying again** when
that service changes its snapshots. One file is ours and **derived**, not copied: `two_tables_two_jobs.txt` (the shape of
`two_tables_one_job.txt` with both tables running, to test all or nothing).

## `dynamics_pending`: the older shape (legacy)

What `Dynamics-Development`, an older version, answered on 2026-11-11, with placeholder data. The Go service keeps its `note:
pending: ...` lines **until at least 2027-01-11** and says ai-agent moves to `dynamics_v1` before then; the protocol stays for a
server that still answers this way.

| File | Provenance |
|---|---|
| `dynamics_pending/first_one_table.txt` | the shape seen on the older server (a `pending` note and a job id), placeholder data |
| `dynamics_pending/first_two_tables.txt` | **assumed**: the same note once per table; never seen |
| `dynamics_pending/read_done_open.txt`, `read_done_archived.txt` | the shape of a job result of the older server |
| `dynamics_pending/read_running.txt` | **assumed**: never seen |
