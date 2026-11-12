# application/dtos/outbound/

What the outbound adapters (`infrastructure/outbound/`) exchange with the application. These are the **domain's own classes**, not copies: each file only exposes them under a path an adapter may import, because an adapter never imports `domain/` (`tests/test_clean_architecture.py`).

| File | Names |
|---|---|
| `llm.py` | `Payload`, `Response`, `SelectedModel` (the LLM port) |
| `tools.py` | `ToolDefinition`, `ToolScope`, `ToolCallRecord` (the MCP port and the tool signals) |
| `usage.py` | `RequestRecord`, `CallDetails` (the usage port) |
| `config.py` | `Loaded`, `ConfigError` (the configuration port) |
