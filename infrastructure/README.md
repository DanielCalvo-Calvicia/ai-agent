# infrastructure/

The **adapters**: the code that talks to the outside world (HTTP clients, LLM providers, MCP servers, files, Langfuse). It implements the ports defined in `application/` and holds no decision logic.

```text
infrastructure/
  inbound/http/     FastAPI routes  ->  calls application/ports/inbound
  outbound/
    llm/            LLMOutboundPort    (Vercel AI SDK: Google, Anthropic, OpenAI, Mistral, Groq, Cohere, Ollama)
    mcp/            McpToolsPort       (MCP client, tool catalog, tool executor, masking of personal data)
    config/         ConfigSourcePort   (profiles, flows, step declarations, model sets, prompts from files)
    usage/          UsageReporterPort  (Langfuse, price files)
```

| Folder | What it is |
|---|---|
| [`inbound/`](inbound/README.md) | How requests enter the service. |
| [`outbound/`](outbound/README.md) | How the service reaches providers, tools, files and monitoring. |

## Rules

- `infrastructure` may import `application` (ports, DTOs) and `domain`; `application` never imports `infrastructure`. Only `composition_root/main.py` wires them together.
- Keep the LLM adapter behind `LLMOutboundPort` so providers stay swappable.
- **No log line, metric or span may hold a tool argument or a tool answer**, and no secret (provider key, token) is ever logged.
