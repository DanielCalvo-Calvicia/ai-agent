# infrastructure/inbound/

Adapters through which **requests enter** ai-agent. Today there is one: HTTP.

| Folder | What it is |
|---|---|
| [`http/`](http/README.md) | The FastAPI routes and the answer envelope. |

An inbound adapter only translates the transport (HTTP body, status codes) to the DTOs and ports of `application/dtos/inbound/` and `application/ports/inbound/` and back. It decides nothing about profiles, flows or steps.
