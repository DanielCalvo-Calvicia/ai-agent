# infrastructure/outbound/

Adapters through which ai-agent **reaches out**. Each folder implements one port of `application/ports/outbound/`.

| Folder | Port it implements | What it talks to |
|---|---|---|
| [`llm/`](llm/README.md) | `LLMOutboundPort` | LLM providers (Google, Anthropic, OpenAI, Mistral, Groq, Cohere, Ollama) |
| [`mcp/`](mcp/README.md) | `McpToolsPort` | MCP servers (`mcps/*.json`; today `dynamics_microservice`, read-only Business Central) |
| [`config/`](config/README.md) | `ConfigSourcePort` | The JSON and prompt files of the repository |
| [`usage/`](usage/README.md) | `UsageReporterPort` | Langfuse and the price files in `config/` |

The composition root builds each adapter and injects it into the application. Secrets (provider keys, Langfuse keys) come from the environment and are never printed.
