# application/outbound/ports/

The **outbound ports**: the interfaces the application calls and `infrastructure/outbound/` implements.

| File | Port / contents | Implemented by |
|---|---|---|
| `llm_ports.py` | `LLMOutboundPort`: `ask(Payload) -> Response \| str` (one stateless LLM call) and `is_available()` (a provider is configured; no network call). | `infrastructure/outbound/llm/vercel.py` (`VercelAIAdapter`) |
| `mcp_ports.py` | `McpToolsPort.list_tools(server)`. The **tool scope** (`ToolLimit`, `ToolScope`, `scoped`): which tools a step may use is what every configured level allows (profile, flow, flow file, step, override). The **tool-failure signal** (`ToolFailures`, `watch_tool_failures`, `report_final_tool_failure`), `ToolCallRecord` and the **wait budget** of the tool calls of one message (`tool_wait_budget`, `spend_tool_wait`). | `infrastructure/outbound/mcp/` (`MCPToolCatalog`, `MCPToolExecutor`) |
| `config_ports.py` | `ConfigSourcePort`: `load_profiles`, `load_flows`, `load_step_defs`, `load_model_sets`, `load_state_fields`, `load_prompt(name)`; `Loaded` (items and errors per file) and `ConfigError`. Read once at start. | `infrastructure/outbound/config/file_source.py` (`FileConfigSource`) |
| `usage_ports.py` | `UsageReporterPort.report(...)` for each LLM call and optionally `report_tool_call(...)`; `CallDetails` (what went in and out). Must never raise. | `infrastructure/outbound/usage/langfuse.py` (`LangfuseUsageReporter`) |

## How they work in the project

- `PhaseRunner` and `Pipeline` receive an `LLMOutboundPort` and an optional `McpToolsPort`; the composition root passes the real adapters.
- `SessionMetrics` (`support/metrics.py`) forwards one record per LLM call to the `UsageReporterPort`.
- Privacy rule: **no tool argument or tool answer** goes into a record, log line or span (name, outcome, duration and tries only).
