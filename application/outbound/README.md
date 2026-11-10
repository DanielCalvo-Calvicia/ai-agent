# application/outbound/

What the application **needs from the outside**, written as interfaces. Nothing here talks to a network or a file: `infrastructure/outbound/` implements it.

| Folder | What it is |
|---|---|
| [`ports/`](ports/README.md) | The ports: LLM, MCP tools, configuration source, usage reporting. |

## How it fits

```text
application/runtime/...  --uses-->  application/outbound/ports/*  <--implemented by--  infrastructure/outbound/{llm,mcp,config,usage}
```

Because the runtime only sees ports, providers stay swappable (an LLM adapter other than the Vercel AI SDK, a configuration source other than files) and every test can use a mock.
