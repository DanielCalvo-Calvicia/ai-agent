# application/ports/outbound/

The **outbound ports**: the interfaces the application calls and `infrastructure/outbound/` implements.

| File | Port / contents | Implemented by |
|---|---|---|
| `llm_ports.py` | `LLMOutboundPort`: `ask(Payload) -> Response \| str` (one stateless LLM call) and `is_available()` (a provider is configured; no network call). | `infrastructure/outbound/llm/vercel/adapter.py` (`VercelAIAdapter`) |
| `mcp_ports.py` | `McpToolsPort`: `list_tools(server)` and `call_tool(...)`. The data (`ToolScope`, `ToolCallRecord`) is in `domain/value_objects/tools/`; the scoping wrapper is in `application/support/tools/`. `tool_failures.py` and `tool_wait_budget.py` are the two **signals** the MCP adapter reports into (a tool call that failed for good, the calls of an attempt, the wait budget of one message), kept here because infrastructure may only depend on the ports. | `infrastructure/outbound/mcp/` (`MCPToolCatalog`, `MCPToolExecutor`) |
| `config_ports.py` | `ConfigSourcePort`: `load_profiles`, `load_flows`, `load_step_defs`, `load_model_sets`, `load_state_fields`, `load_prompt(name)`; Read once at start. Its `Loaded` is in `domain/value_objects/config/` and `ConfigError` in `domain/errors/`. | `infrastructure/outbound/config/file_source.py` (`FileConfigSource`) |
| `usage_ports.py` | `UsageReporterPort.report(...)` for each LLM call and optionally `report_tool_call(...)`; `CallDetails` is in `domain/value_objects/usage/`. Must never raise. | `infrastructure/outbound/usage/langfuse.py` (`LangfuseUsageReporter`) |

## How they work in the project

- `PhaseRunner` and `Pipeline` receive an `LLMOutboundPort` and an optional `McpToolsPort`; the composition root passes the real adapters.
- `SessionMetrics` (`runtime/step/metrics.py`) forwards one record per LLM call to the `UsageReporterPort`.
- Privacy rule: **no tool argument or tool answer** goes into a record, log line or span (name, outcome, duration and tries only).
