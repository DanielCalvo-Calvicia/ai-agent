# shared/providers/

No SDK is imported here.

| File | Contents |
|---|---|
| `config.py` | `LLMConfig.from_env()`: provider keys and base URLs, read when called (not at import), so a `.env` loaded at start is respected; carries the MCP tool executor. Keys are never printed. |
| `routes.py` | The table of OpenAI-compatible routes (a provider is one row), `openai_compatible_credentials` and `ErrProviderNotSupported`. |
| `availability.py` | `any_provider_configured`: a key or `OLLAMA_URL` is set. |
