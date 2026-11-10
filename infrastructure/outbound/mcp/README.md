# infrastructure/outbound/mcp/

The **MCP client side**: reads the tools of the configured MCP servers and runs them. Today the only server in use is `dynamics_microservice` (Business Central, **read-only**, Streamable HTTP; `mcps/dynamics_microservice.json`, URL in `DYNAMICS_MCP_URL`).

| File | Contents |
|---|---|
| `config.py` | Loads `mcps/*.json` (`load_mcp_configs`, `load_supported_mcp_configs`: only `sse` and `streamable_http`); `${NAME}` in a value becomes that environment variable; a server with an unset variable is skipped. `load_tool_snapshot`. |
| `client_manager.py` | `MCPClientManager.session_scope(server)`: opens a session (SSE or Streamable HTTP). `quiet_client_libraries()` keeps `httpx`, `httpcore` and `mcp.client` at WARNING so no URL or argument reaches a log. |
| `tool_catalog.py` | `MCPToolCatalog`: lists a server's tools (only those in its `allowed_tools`), keeps a successful listing for the life of the process and a failed one for 60 s; `call_timeout_seconds()` (`AI_AGENT_MCP_CALL_TIMEOUT_SECONDS`, 30). |
| `tool_executor.py` | `MCPToolExecutor` implements `McpToolsPort`: `list_tools` and `execute(tool, args, scope)`. Refuses a tool outside the step's `ToolScope`, retries once only after a transport error or `error (retry_later)`, measures each call (tool, outcome, duration, tries) and applies the personal-data mask. |
| `masking.py` | Replaces cells of personal columns (customer name, e-mail, phone, address, contact, VAT, bank) with `[hidden]` before a tool answer reaches any model, provider log or Langfuse. `AI_AGENT_MASK_PERSONAL_DATA=0` turns it off. |
| `availability.py` | `McpAvailabilityCheck`: optional (`AI_AGENT_CHECK_MCP_<NAME>=1`) reachability check at start and on `/available`; logs only, never changes an answer. |

## Rules

**No log line, metric or span may hold a tool argument or a tool answer.** Only the tool name, outcome, duration and number of tries are recorded.
