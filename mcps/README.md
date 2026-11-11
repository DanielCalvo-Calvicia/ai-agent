# mcps/

One JSON file per group of MCP (Model Context Protocol) servers the agent may call as tools. Read at start by `infrastructure/outbound/mcp/config.py`. A **profile** decides which of these servers a step may use (`tools` in [profiles/README.md](../profiles/README.md)); this folder only says **what exists and how to reach it**.

This folder is not read through the configuration source of the other four (no `schema_version`, no `name` check), and **a file whose name starts with `_` is still loaded** here (it is not skipped as in `profiles/` or `flows/`). To disable a server, move the file out of the folder or remove its `url` variable.

## 1. File format

A file is an object whose **keys are server names** and whose values are the server's settings. One file may hold several servers; the file name is free (the server name is the key, not the file name).

```json
{
    "dynamics_microservice": {
        "type": "streamable_http",
        "url": "${DYNAMICS_MCP_URL}",
        "allowed_tools": ["customer_orders", "order_status", "customer_card"]
    }
}
```

| Field | Required | Values | Meaning |
|---|---|---|---|
| (key) | yes | text, unique across all files | The server name. It is what a profile writes in `tools.servers`, what the planner sees as `server_id` and what metrics show. Do not repeat a name in two files: nothing checks it and the result is unreliable. |
| `type` | no | `"sse"`, `"streamable_http"` | The transport. **Missing means `stdio`, which this agent does not support**: the server is ignored with a warning. Only these two work (`SUPPORTED_TYPES`). |
| `url` | yes for the two types | text; may contain `${NAME}` | Where the server is. `${NAME}` is replaced by the environment variable `NAME` in **every string of the file**; a variable that is not set stays as written. If the `url` still holds a `${...}` after the replacement, the server is **skipped with a warning** (this is how `DYNAMICS_MCP_URL` unset turns the server off). |
| `allowed_tools` | no | list of tool names | A whitelist. Without it the server offers **every** tool it lists. With it, only these tools reach the model; the others are hidden and logged at WARNING. It also lets `scripts/check_agent.py` check a profile's `server.tool` names (see section 3). |
| `job_protocol` | no | `"none"` (the default), `"dynamics_v1"`, `"dynamics_pending"` | How an answer that is a job still running is found and followed to its result (ADR-018, T-07). `none`: the server has no jobs, an answer is the result whatever it says. `dynamics_v1`: the jobs contract of `dynamics_microservice` since 2026-11-11 (`status: running` with a `job_id`, per table). `dynamics_pending`: the older shape (`note: pending: … job <id> …`), legacy. A name that is not one of these skips the server with a warning. |
| `job_read_tool` | with a `job_protocol` other than `none` | tool name | The tool that reads a job (`get_job_result`). Must be in `allowed_tools` if the file has the list. Only this tool is called to read a job, only with the id the protocol found in the answer. |
| `job_cancel_tool` | no | tool name | The tool that stops a job whose time ran out (`cancel_job`). Must be in `allowed_tools` if the file has the list. Without it a job that does not end is left running and the answer says it is still running. |

Any other key (`command`, `args`, `env`, `headers`, ...) is read but **not used** for `sse` and `streamable_http`. In particular **there is no way to send an authentication header**: the only header sent is the trace context (`traceparent`). A server that needs a key cannot be added without a code change.

## 2. The files here

| File | Type | State |
|---|---|---|
| `dynamics_microservice.json` | `streamable_http`, `${DYNAMICS_MCP_URL}` | **In use.** Read-only Business Central tools (ADR-011): orders, customer card, SEUR shipments. `allowed_tools` is the list of what the agent may call; `job_protocol` is `dynamics_v1`. |
| `aws_microservice.json` | `sse`, a fixed local URL | Loaded, but no profile has tools that reach it and nothing uses it. |
| `fetch.json`, `filesystem.json` | `stdio` (Docker) | **Ignored at run time** (unsupported type). They still count as existing servers for the check of a profile, which would pass and then offer no tools. `filesystem.json` also needs `MCP_FILESYSTEM_DIR`. |

## 3. How a server reaches a step

1. A server is **available** if its type is supported and its `url` has no unset variable.
2. A step sees a server only if **every level of its tool scope allows it** (profile `tools`, `flows.<flow>.tools`, the flow file's `tools`, the step's `tools` in the flow file, `overrides.<step>.tools`). A profile with no `tools` at all gets **every available server**: that is why every shipped profile except `special` states its `tools` (`default` has `{"servers": []}`: no tools, on purpose).
3. A server that is available but returns no tools for a message (it is down, or none of its tools is in `allowed_tools`) is left out of that message's plan. A failed listing is not asked again for 60 seconds.
4. Only the **planner** (`project_manager`) chooses servers; `mcp_operator` runs one tool call per action.

How tool names are written in a profile (checked by `scripts/check_agent.py`):

| In a profile | Meaning | Check |
|---|---|---|
| `"servers": ["dynamics_microservice"]` | every tool of that server | the server must exist in `mcps/` (any `type`) |
| `"tools": ["dynamics_microservice.customer_orders"]` | one tool | the server must list it in `allowed_tools`; **a server with no `allowed_tools` cannot be used this way** |
| `"tools": ["customer_orders"]` | one tool, bare name | exactly one server may own it; if two do, write `server.tool` |

## 4. Limits and behaviour you cannot configure here

- **Read-only is a rule of the service, not of this file.** Keep `allowed_tools` to tools that cannot change data. Never add a server that can write without a decision (ADR-011).
- Each tool call may take `AI_AGENT_MCP_CALL_TIMEOUT_SECONDS` (30); the calls of one message may wait 60 s in total; one message runs at most `AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE` tool actions (5, `0` = no limit). All in [docs/configuration/environment-variables.md](../docs/configuration/environment-variables.md).
- Personal columns of a tool answer (name, e-mail, phone, address, VAT, bank number) are replaced by `[hidden]` before the answer goes to any model, unless `AI_AGENT_MASK_PERSONAL_DATA=0` (`infrastructure/outbound/mcp/masking.py`). The masking looks for table answers with cells separated by `|` (the shape `dynamics_microservice` returns); another server's answers are not masked unless they have that shape.
- **No log line, metric or span holds a tool argument or answer**: only the tool name, outcome, duration and tries.
- `AI_AGENT_CHECK_MCP_<NAME>=1` (`<NAME>` is the server name in upper case, other characters as `_`) makes the service list that server's tools at start and on `/available`, and only logs whether it answered.
- Servers are read **at start**: restart the service after editing a file.

## 5. Adding a server

1. Create `mcps/<name>.json` with the key, `type` (`sse` or `streamable_http`), a `url` (use `${VAR}` for anything machine-specific and add the variable to `.env.example` and the environment document), and an `allowed_tools` list.
2. Decide who may use it: add it to `tools.servers` of the profiles that need it and leave it out of the rest. Profiles with no `tools` get it automatically.
3. Run `python scripts/check_agent.py` (it reads this folder) and then `python scripts/check_agent.py --explain <profile>` to see which tools each step ends up with.
4. Update `docs/api/api.md` ("Tools consumed") and `docs/security/security.md` (what data the server can reach and what reaches the model provider).
