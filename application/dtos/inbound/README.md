# application/dtos/inbound/

Data Transfer Objects (Pydantic models) of the requests the service receives and the answers it gives. They carry data only.

| File | Contents |
|---|---|
| `base_request.py` | `BaseRequestDTO` (`request_id`, `user_id`, `correlation_id`, `metadata`, `timestamp`; `extra="forbid"`) and `BaseResponseDTO` (`success`, `message`, `error_code`, `correlation_id`). Every other DTO extends them. |
| `session.py` | The DTOs of the three session operations: `StartSession*`, `EndSession*` and `MessageReceived*`. `MessageReceivedRequestDTO` carries `session_id`, `message`, `speak_movements` and the optional profile fields (`profile`, `token`, `inputs`, `return` as `return_`, `pause_id`, `client`). `MessageReceivedResponseDTO` carries `response`, `movements`, `gesture`, `awaiting_user_input`, `flow` and, when they apply, `profile`, `output`, `pause_id`, `discarded_pause`. |
| `message.py` | The DTOs of one message inside the application (`TextRequestDTO`, `TextResponseDTO`, audio versions) and the enums `MessageType`, `StepStatus`, `InteractionStatus`, `ControlType`. `MessageFlowService.text()` uses `TextRequestDTO` / `TextResponseDTO`. |

## How they work in the project

- `infrastructure/inbound/http/fastapi.py` converts the contract request into a `MessageReceivedRequestDTO`, calls the service, and converts the `MessageReceivedResponseDTO` into the contract answer (`contracts.api.microservices.ai_agent.session`).
- `SessionService` converts a `MessageReceivedRequestDTO` into a `TextRequestDTO` for `MessageFlowService`, and the `TextResponseDTO` back.
- The profile fields are read from ai-agent's own request model until the `contracts` repository has them (`docs/api/api.md`).
- `token` is `repr=False` and is never logged.

When you add a field to an answer, update `docs/api/api.md` and `docs/requirements/requirements.md` too.
