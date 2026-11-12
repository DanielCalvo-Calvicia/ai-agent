# infrastructure/outbound/llm/vercel/

Everything here imports `ai_sdk`. The decisions (which key, which tools, which schema) are in `../shared/`.

| File | Contents |
|---|---|
| `adapter.py` | `VercelAIAdapter` implements `LLMOutboundPort`: builds the model, messages and options, calls `ai_sdk.generate_text`, maps the answer. `is_available()` only checks that a key or `OLLAMA_URL` is set (no network call). |
| `models.py` | `create_model` / `resolve_provider_model`: a domain model to an `ai_sdk` model (OpenAI and Anthropic native, the rest through their OpenAI-compatible endpoint). |
| `messages.py` | `build_messages`: the system and user messages. |
| `options.py` | `build_options`: seed, response format (sanitized for Claude) and tools. |
| `tool_adapter.py` | `resolve_tools`: `ToolSpec` objects into `ai_sdk` `Tool`s. |
