# application/ports/inbound/

The **inbound ports**: the interfaces (abstract classes) the application offers to whoever calls it. A service implements them; an adapter (HTTP) calls them.

| File | Port | Methods | Implemented by |
|---|---|---|---|
| `session.py` | `SessionInboundPort` | `start_session`, `end_session`, `message_received`, `is_available` (true when a provider key or `OLLAMA_URL` is configured; never calls an LLM) | `application/service/session_service.py` (`SessionService`) |
| `message_flow_ports.py` | `MessageInboundPort` | `text(TextRequestDTO) -> TextResponseDTO` (its constructor receives the LLM port, the MCP list, history and the paused run) | `application/service/message_flow_service.py` (`MessageFlowService`) |

## How they work in the project

`SessionFastAPI` holds a `SessionInboundPort`, not a `SessionService`. `SessionService` creates one `MessageFlowService` per message through `MessageInboundPort`. Keeping the ports abstract lets the tests replace either side with a mock and lets another transport reuse the same application.
