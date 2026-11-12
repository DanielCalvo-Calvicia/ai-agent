# application/

The **application layer** of ai-agent: everything that decides what to do with a user's message, with no knowledge of HTTP, of a particular LLM provider or of an MCP library. It talks to the outside only through **ports** (abstract classes) that `infrastructure/` implements.

```text
infrastructure/inbound/http  ->  application/{dtos,ports}/inbound  ->  application/service  ->  application/runtime  ->  application/ports/outbound  ->  infrastructure/outbound
                                   (DTOs, ports)           (sessions, one message)  (profile, flow, step)      (what the agent needs)           (LLM, MCP, config, usage)
```

## Rules

- `application` never imports `infrastructure`. `composition_root/main.py` is the only place that wires both.
- `application` may import `domain/` (pure data). `domain/` never imports `application`.
- Inside the runtime, dependencies go one way: **profile -> flow -> step -> state -> support**. `tests/test_orchestration_layout.py` enforces it.
- Between the layers they go one way too: **service -> assembly -> runtime -> support -> ports, dtos -> domain**, and the application opens no file and reads no environment variable (`support/environment.py`). `tests/test_clean_architecture.py` enforces it.

## Sub-folders

| Folder | What it is |
|---|---|
| [`dtos/`](dtos/README.md) | `dtos/inbound/` (request/answer DTOs) and `dtos/outbound/` (the domain's own classes the outbound adapters use). |
| [`mappers/`](mappers/README.md) | The conversions at the edges: `inbound/` (message request and answer DTOs) and `outbound/` (the LLM's JSON into a domain `Response`). |
| [`ports/`](ports/README.md) | The interfaces: `ports/inbound/` (what the outside world calls, implemented by the services) and `ports/outbound/` (what the application needs from the outside: LLM, MCP tools, configuration, usage reporting). |
| [`service/`](service/README.md) | The services behind the ports: sessions (`SessionService`) and one message (`MessageFlowService`). |
| [`runtime/`](runtime/README.md) | The path of a message: profile, flow, step, state. This is the "mind". |
| [`assembly/`](assembly/README.md) | Start-up only: reads the configuration, checks it and builds the `Agent` (defined in `runtime/profile/assembled.py`) the runtime uses. |
| [`support/`](support/README.md) | Shared helpers: metrics, clock, model selection, schemas, failures, tool helpers. |

## How a message travels (short version)

1. `SessionFastAPI` (infrastructure) turns the HTTP body into a DTO and calls `SessionInboundPort.message_received`.
2. `SessionService` finds the session, checks the profile and its token, and builds a `MessageFlowService`.
3. `MessageFlowService` asks `ProfileRunner` to run **one profile** (one flow of steps).
4. The `Pipeline` runs each step; each LLM step goes through `PhaseRunner` and `LLMOutboundPort`.
5. The result (`FlowResult`) goes back up as a DTO: what to say, the movements, and whether the agent waits for the user.

Full description: [`docs/architecture/architecture.md`](../docs/architecture/architecture.md).
