# application/ports/

The **interfaces** (abstract classes) of the application, in two directions. They hold no logic and talk to no network or file.

| Folder | What it is |
|---|---|
| [`inbound/`](inbound/README.md) | What the outside world (today only the HTTP layer) calls. Implemented by the services in `application/service/`. |
| [`outbound/`](outbound/README.md) | What the application needs from the outside: LLM, MCP tools, configuration source, usage reporting. Implemented by `infrastructure/outbound/`. |

The shapes that travel through the inbound ports (request and answer objects) are in [`application/dtos/inbound/`](../dtos/inbound/README.md).

## How it fits

```text
infrastructure/inbound/http/fastapi.py  --builds-->  dtos/inbound/*  --calls-->  ports/inbound/SessionInboundPort
                                                                                       ^ implemented by application/service/session_service.py

application/runtime/...  --uses-->  ports/outbound/*  <--implemented by--  infrastructure/outbound/{llm,mcp,config,usage}
```

The HTTP adapter depends on the inbound ports, never on the concrete service, so another transport (a queue, a CLI) could replace HTTP. The runtime only sees the outbound ports, so providers stay swappable and every test can use a mock.
