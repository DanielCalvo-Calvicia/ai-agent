# application/runtime/step/library/special/

Code for the `special` / `dynamics` / `default` flows.

| File | Contents |
|---|---|
| `action_executor.py` | `ActionExecutor` (built by `build_step`): runs the actions the project manager planned **in dependency order**, one LLM call each. An action is ready when its subactions and the actions it depends on are settled (done or failed); it receives their outputs. An action of type `mcp_tool_call` uses the tool caller (`mcp_operator`) and the MCP tools its `ToolScope` allows; any other action uses the cognitive worker. Independent actions may run in parallel (`AI_AGENT_PARALLEL_ACTIONS`, default 1). |

## Limits and rules

- At most `AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE` tool actions per message (5; `0` = no limit) and a total tool wait of 60 s.
- An MCP action is blocked until the user confirms when the safety gate asks for confirmation (`BLOCKED_BY_CONFIRMATION`).
- Failures use `support/llm/failure.py` (`AgentFailure`); tool failures leave a signal through `outbound/ports/mcp_ports.py`.
- No log or metric may hold a tool argument or a tool answer.
