# application/support/tools/

Helpers about **tools and planned actions**.

| File | Contents |
|---|---|
| `action_tree.py` | Looks inside the tree of actions the project manager plans: `subactions_of` (dict or list storage), `action_type_of`, `in_execution_order`, `with_outputs`, `mark_mcp_actions_blocked` (until the user confirms), constants `MCP_ACTION_TYPE` and `BLOCKED_BY_CONFIRMATION`. Used by the action executor. |
| `scoped_tools.py` | `ScopedTools` (the tools port a step sees: only the tools its scope allows) and `scoped()`. |
| `mcp_servers.py` | `server_names` and `describe_servers`: how the MCP servers are shown to the planner (name, tools, descriptions, parameters; never connection settings). A server that offers no tools for this message is left out. |

Which tools a step may use is decided by `ToolScope` (`domain/value_objects/tools/tool_scope.py`); these helpers only describe what is allowed.
