# infrastructure/outbound/mcp/

The **MCP client side**: reads the tools of the configured MCP servers and runs them, with no LLM. Today the only server in use is `dynamics_microservice` (Business Central, **read-only**, Streamable HTTP; `mcps/dynamics_microservice.json`, URL in `DYNAMICS_MCP_URL`).

```
mcp/
  server.py                  McpServer: a frozen view of one server entry (type, url, allowed_tools, job settings)
  config/
    loader.py                loads mcps/*.json; ${NAME} in a value is that environment variable; load_tool_snapshot
  connection/
    client_manager.py        opens a session (SSE or Streamable HTTP); quiet_client_libraries()
    limits.py                the waits: listing 10 s, 60 s quiet after a failed listing, call limit (30 s)
    call_result.py           answer dicts, kind of a tool error, timeout test, error class names
  catalog/
    tool_catalog.py          which server offers which tool (only its allowed_tools); listings are kept
    availability.py          optional reachability check (AI_AGENT_CHECK_MCP_<NAME>=1), logs only
  execution/
    tool_executor.py         McpToolsPort: list_tools, call_tool, execute(tool, args, scope)
    masking.py               hides personal columns of an answer (AI_AGENT_MASK_PERSONAL_DATA=0: off)
  jobs/                      the follow-up of a tool answer that is a job (ADR-018)
    protocol.py  registry.py  settings.py  follow_up.py  protocols/
```

Grouped by usage: **config** reads the files, **connection** reaches a server, **catalog** knows what a server offers, **execution** runs one call (and uses `jobs/` when an answer is a job). Who uses whom: `execution` uses `catalog`, `connection` and `jobs`; `catalog` uses `connection`, `config` and `server.py`; `connection` and `config` use only `server.py` and `jobs/settings.py` (to check a server file); `jobs/` uses nothing else of this folder.

| File | Contents |
|---|---|
| `config/loader.py` | `load_mcp_configs`, `load_supported_mcp_configs` (only `sse` and `streamable_http`, and only a server whose job settings can work; one with an unset `${NAME}` is skipped), `load_tool_snapshot`. |
| `connection/client_manager.py` | `MCPClientManager.session_scope(server)`. `quiet_client_libraries()` keeps `httpx`, `httpcore` and `mcp.client` at WARNING so no URL or argument reaches a log. |
| `catalog/tool_catalog.py` | `MCPToolCatalog`: lists a server's tools, keeps a successful listing for the life of the process and a failed one for 60 s. |
| `execution/tool_executor.py` | `MCPToolExecutor`: refuses a tool outside the step's `ToolScope`, retries once only after a transport error or `error (retry_later)`, hands a job answer to `jobs/`, measures each call (tool, outcome, duration, tries), applies the personal-data mask. |
| `connection/call_result.py` | The answer dicts (`success`, `failure`), the kind of a tool error, the timeout test, the class names of an error (`error_types`, never its text). Used by `catalog/` and `execution/`. |
| `execution/masking.py` | Replaces cells of personal columns (customer name, e-mail, phone, address, contact, VAT, bank) with `[hidden]` before a tool answer reaches any model, provider log or Langfuse. |

## `jobs/`

| File | Contents |
|---|---|
| `protocol.py` | `JobProtocol` (the interface: `detect`, `read_arguments`, `state`, `merge`, `cancel_arguments`), `JobRef`, `NoJobs` (`none`, the default) and the states `DONE`, `RUNNING`, `UNKNOWN`. |
| `registry.py` | The protocols by name: `get_protocol`, `known_protocols`. A new protocol is one file in `protocols/` and one entry here. |
| `settings.py` | `job_protocol_problem`: why the job settings of a server file cannot work (`config/loader.py` ignores such a server at start). |
| `follow_up.py` | The loop: reads with a wait of 1 s doubling to 5 s, all or nothing for several jobs, cancels what still runs when the time is spent. It makes no call itself. |
| `protocols/` | `dynamics_v1` (the contract of `dynamics_microservice` since 2026-11-11), `dynamics_pending` (the older shape, legacy), `common.py` (what they share). |

Imports go one way: `protocol.py` <- `protocols/` <- `registry.py` <- `settings.py` <- `config/loader.py`; nothing is imported lazily. `tests/test_mcp_server_and_results.py` imports each one first, alone.

## Rules

**No log line, metric or span may hold a tool argument or a tool answer.** Only the tool name, outcome, duration and number of tries are recorded.
