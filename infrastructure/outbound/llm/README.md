# infrastructure/outbound/llm/

The **LLM adapter**: one stateless call per `ask`, system prompt + user message in, a domain `Response` out. The folder is split by who knows the SDK (2026-11-12):

| Folder | Contents |
|---|---|
| `vercel/` | The only code that imports `ai_sdk` (the Python AI SDK). See its README. |
| `shared/providers/` | Provider keys and URLs, the route table, the availability check. No SDK. |
| `shared/tools/` | Turns the tools of a payload into `ToolSpec` objects. No SDK. |
| `shared/schemas/` | Schemas that belong to one provider (today: the Anthropic sanitizer). No SDK. |

`tests/test_llm_layout.py` fails when a file of `shared/` imports `ai_sdk`, or when a file outside `vercel/` does.

## How it works in the project

`PhaseRunner` builds a `Payload` (model, system prompt, message, response format, tools) and calls `LLMOutboundPort.ask`. `VercelAIAdapter` picks the provider from the model, sends the call and returns a `Response` (built by `application/mappers/outbound/response_mapper.py`); failures are classified upstream by `application/support/llm/failure.py`. Prices of the models are in `config/` and used by `usage/`.
