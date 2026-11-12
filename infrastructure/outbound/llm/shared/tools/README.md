# shared/tools/

No SDK is imported here.

| File | Contents |
|---|---|
| `spec.py` | `ToolSpec`: name, description, JSON Schema of the arguments, handler. |
| `resolver.py` | `resolve_tool_specs`: expands an MCP server descriptor through the tool executor (skipped without one), honours its `ToolScope`, turns a `ToolDefinition` into a `ToolSpec`; an entry that already has a handler is kept. |
| `handlers.py` | `handler_for`: runs the tool through the executor (with its scope), or answers a mock success without one. |
