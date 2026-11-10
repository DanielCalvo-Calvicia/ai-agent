# application/inbound/

What the **outside world** (today only the HTTP layer) uses to talk to the application. It holds no logic: only the shapes of what comes in and goes out (`dto/`) and the interfaces the services implement (`ports/`).

| Folder | What it is |
|---|---|
| [`dto/`](dto/README.md) | Pydantic request/answer objects. |
| [`ports/`](ports/README.md) | Abstract classes implemented by the services in `application/service/`. |

## How it fits

```text
infrastructure/inbound/http/fastapi.py  --builds-->  dto/*  --calls-->  ports/SessionInboundPort
                                                                              ^ implemented by application/service/session_service.py
```

The HTTP adapter depends on these ports, never on the concrete service, so another transport (a queue, a CLI) could replace HTTP without touching the application.
