# infrastructure/outbound/llm/

The **LLM adapter**: one stateless call per `ask`, system prompt + user message in, a domain `Response` out.

| File | Contents |
|---|---|
| `vercel.py` | `VercelAIAdapter` implements `LLMOutboundPort` with the Python AI SDK (`ai_sdk.generate_text`): builds the messages and options, applies the schema format, calls the model and maps the answer. `is_available()` only checks that a key or `OLLAMA_URL` is set. |
| `config.py` | `VercelAIConfig.from_env()`: provider keys and base URLs, read when called (not at import), so a `.env` loaded at start is respected; carries the MCP tool executor. Keys are never printed. |
| `provider_models.py` | `create_model` / `resolve_provider_model`: maps a domain model to an ai_sdk model. OpenAI and Anthropic native; Google, Mistral, Groq, Cohere and Ollama through their OpenAI-compatible endpoints. |
| `anthropic_schema.py` | Turns a step's JSON Schema into the subset Anthropic's strict structured output accepts (`additionalProperties: false`, unsupported keywords removed, recursive actions unrolled to 3 levels). Only Claude models use it (ADR-013). |
| `tools.py` | `resolve_tools`: turns the tools of a payload into ai_sdk tools, expanding an MCP server descriptor through the tool executor and honouring its `ToolScope`. |
| `response_mapper.py` | `build_response` / `read_response_json`: turns the model's text or JSON into the domain `Response`, one small function per section (also reads the sections a client sends back in `inputs`). Includes token usage. |

## How it works in the project

`PhaseRunner` builds a `Payload` (model, system prompt, message, response format, tools) and calls `LLMOutboundPort.ask`. The adapter picks the provider from the model, sends the call and returns a `Response`; failures are classified upstream by `application/support/llm/failure.py`. Prices of the models are in `config/` and used by `usage/`.
