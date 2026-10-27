# Tasks

Hierarchical task plan, same format as `dynamics_microservice/docs/tasks`. Epics so far: **T-01 use the `dynamics_microservice` MCP tools from ai-agent** (todo, created 2026-10-27). It is written to be executed step by step: every leaf task states what to create or change, what it must not do and how to prove it is done.

The order, with the state and date of each task, is in [ORDER.md](ORDER.md). The board is in section 5. The prompts to start or resume the build in another session are in [PROMPTS.md](PROMPTS.md).

## 1. Structure and naming

- Every task is a Markdown file. A task with subtasks lives in a folder of the same name, and its own file has the same name inside that folder. Leaves are single files.
- IDs are hierarchical and stable: `T-01` -> `T-01.3`. Never reuse or renumber an ID.
- A parent describes goal, order and exit criteria; **leaves carry the implementation detail**.
- Every task file starts with a table: `Status`, `Kind`, `Parent`, `Depends on`, `Blocks`, `Size` (S, M, L), then *Goal*, *Files*, *Specification*, *Acceptance criteria*, *Verification* and, once started, *Notes*.

```text
docs/tasks/
├── README.md                                   (this file)
├── ORDER.md                                    the order, the state and the date of every task
└── T-01_dynamics-mcp/                          epic
    ├── T-01_dynamics-mcp.md
    └── T-01.1_decisions.md ... T-01.12_tool-call-metrics.md      leaves (T-01.10 to T-01.12 were added after Q03 and Q04)
```

## 2. Execution protocol

1. Pick the first task whose status is `todo` and whose `Depends on` tasks are all `done`. A `decision` task that is `awaiting-user` **stops the chain**: ask the user, record the answer in its *Resolution*, then continue.
2. Read `CLAUDE.md`, `docs/architecture/architecture.md` and the documents the task names before touching code.
3. Create or modify only the files listed under *Files* (tests included). Another file, folder or dependency means updating the task first.
4. Implement, then run the task's *Verification* and the baseline of section 3. A task is `done` only when every acceptance criterion passes.
5. Set its `Status` (and its row in section 5 and in `ORDER.md`), update the parent if its exit criteria are met, and record any new fact or deviation in *Notes*.
6. Never edit generated files by hand (the schema tree, `docs/models/*`).
7. All work of epic T-01 goes on the one branch `feature_dynamics_mcp` (no branch per task, Q04-5). Do not commit, push or open a pull request unless the user asks. Do not run anything that calls a real LLM or the real service without asking: it costs money.

Status values: `todo`, `awaiting-user`, `blocked`, `in-progress`, `done`.

## 3. Baseline definition of done (every code task)

- `python -m pytest tests` passes (mock-based, no keys, no network). The `windows` venv must exist; if it does not, create it with **Python 3.14** (`py -3.14 -m venv windows`, then `pip install -r requirements.txt`) and **ask once more right before installing** (Q04-7). The folder is git-ignored.
- `python scripts/split_schemas.py` reports no drift of the schema tree.
- A change to a prompt, schema, model or message format changes `tests/golden/flow_golden.json`: read the diff first, then regenerate on purpose (`UPDATE_GOLDEN=1`).
- The layering tests stay green (`test_orchestration_layout.py`, `test_phase_structure.py`); `domain/` imports nothing of the application, `application/` never imports `infrastructure/`.
- Keep the LLM adapter behind `LLMOutboundPort`; every phase file keeps its constants at the top.
- Code reads like the surrounding code: same comment density, naming and idiom.
- No secret, token or real customer data in code, tests, fixtures, prompts or documents; `.env` values are never printed. **No log line, metric or span holds a tool argument or a tool answer** (Q02-7). Hosts, tenants, environments and companies of Business Central are placeholders only.
- The documents that describe the change are true again (the table in `CLAUDE.md`).
- The Go project (`dynamics_microservice`) is **read-only** for this plan: never modify it.

## 4. Facts the tasks rely on

Verified on 2026-10-27 against both projects.

| # | Fact |
|---|---|
| F1 | `dynamics_microservice` serves MCP at `POST /mcp` (`MCP_PATH`) on the same port as its REST API: **Streamable HTTP**, stateless, plain JSON answers, no event stream; `GET` and `DELETE` answer 405; no authentication (`docs/api/mcp.md`, ADR-025 of that project). |
| F2 | Its tools: workflows `customer_orders`, `order_status`, `customer_card`; `list_workflows`, `get_guidance`, `get_job_result`, `cancel_job`; and, only with `MCP_EXPOSE_GENERIC_TOOLS=true` (default), `list_tables`, `describe_table`, `plan_query`, `run_query`. All read-only. |
| F3 | Every tool that reaches Business Central takes optional `environment` and `company`; the server defaults them (`MCP_ENVIRONMENT`, `MCP_COMPANY`). |
| F4 | A call waits up to `MCP_JOB_WAIT` (20 s) for its query; when it is not done the answer is `status: running` with a `job_id` and `next_offset`, read with `get_job_result`. |
| F5 | Answers are a few metadata lines (`returned`, `total`, `coverage`, `hint`) and a table delimited with `\|`, capped at 500 rows and 65,536 bytes. A failed call is a tool error `error (<kind>): <message>` with kind `input`, `not_found`, `retry_later`, `source_problem` or `internal`. |
| F6 | ai-agent MCP client: `SUPPORTED_TYPES = ("sse",)` in `infrastructure/outbound/mcp/config.py`; `client_manager.py` opens every session with `sse_client`; `tool_catalog.py` skips any type other than `sse`; one session per call. |
| F7 | `SERVER_TIMEOUT_SECONDS = 10` in `tool_catalog.py`, used by listing and by `tool_executor.py`, covers the whole session (connect, initialize, call). |
| F8 | `mcps/*.json` are expanded with `${NAME}` by `expand_env`; a variable that is not set stays as written. `mcps/aws_microservice.json` is SSE at `http://localhost:8080/mcp/sse`; `fetch` and `filesystem` are stdio (skipped). |
| F9 | `prompts/capabilities.txt` ends with "No external service is connected"; the triage prompt's CAPABILITY CHECK treats any external service as impossible. |
| F10 | `task_category.domain` picks the flow; `data` (like any value other than `communication` and `movement`) goes to the special flow, whose project manager plans `mcp_tool_call` actions from the tool list. Phase 5 runs one action (one LLM call), phase 6 cleans the result. |
| F11 | Langfuse, when its keys are set, stores the user's text, the prompts and the answers of every call. For this epic that is accepted on purpose, with a trusted project, so the maintainer can see the data in the prototype (Q01-5 B, Q02-6 A). |
| F12 | A session keeps, for each earlier exchange, the user message and the reply that was sent (`AI_AGENT_HISTORY_TURNS`, default 6); triage and the project manager read them. Tool answers are not stored (Q04-1 A). |
| F13 | The MCP tool retry loop is in `application/orchestration/flows/action_executor.py` (`for attempt in range(max_attempts())`); `AI_AGENT_MAX_ATTEMPTS` (3) is shared with LLM calls and `retry` answers. |

## 5. Status board

| ID | Task | Kind | Status |
|---|---|---|---|
| [T-01](T-01_dynamics-mcp/T-01_dynamics-mcp.md) | **Use the dynamics_microservice MCP tools** (epic) | epic | todo |
| [T-01.1](T-01_dynamics-mcp/T-01.1_decisions.md) | Decisions | decision | done (2026-10-27) |
| [T-01.2](T-01_dynamics-mcp/T-01.2_streamable-http-transport.md) | Streamable HTTP transport in the MCP client | code | todo |
| [T-01.3](T-01_dynamics-mcp/T-01.3_server-config-and-settings.md) | Server config and settings | code | todo (after T-01.2) |
| [T-01.4](T-01_dynamics-mcp/T-01.4_mcp-timeouts.md) | Timeouts and retries that fit a slow query | code | todo (after T-01.2) |
| [T-01.5](T-01_dynamics-mcp/T-01.5_capabilities-and-triage-prompts.md) | Tell the agent it has Business Central data | code | todo (after T-01.3) |
| [T-01.6](T-01_dynamics-mcp/T-01.6_planner-guidance-and-jobs.md) | Planner: guidance, jobs and answers | code | todo (after T-01.5, T-01.10 and T-01.11) |
| [T-01.10](T-01_dynamics-mcp/T-01.10_server-availability.md) | Server availability: hide, cache, check, log | code | todo (after T-01.3) |
| [T-01.11](T-01_dynamics-mcp/T-01.11_tool-call-cap.md) | Cap of MCP tool calls per message | code | todo (after T-01.2) |
| [T-01.12](T-01_dynamics-mcp/T-01.12_tool-call-metrics.md) | Tool call metrics | code | todo (after T-01.2 and T-01.4) |
| [T-01.7](T-01_dynamics-mcp/T-01.7_verification.md) | Verification with scripted LLMs | test | blocked (T-01.2 to T-01.6, T-01.10 to T-01.12) |
| [T-01.8](T-01_dynamics-mcp/T-01.8_documentation.md) | Documentation and ADR | docs | blocked (T-01.2 to T-01.6, T-01.10 to T-01.12) |
| [T-01.9](T-01_dynamics-mcp/T-01.9_first-real-run.md) | First real run | manual | blocked (T-01.7, T-01.8) |
