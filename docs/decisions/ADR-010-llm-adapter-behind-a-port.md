# ADR-010 — The LLM adapter sits behind `LLMOutboundPort`

**Status:** Accepted (2026-09-22)

## Decision

All LLM access goes through `LLMOutboundPort`; `VercelAIAdapter` (`infrastructure/outbound/llm/vercel.py`, on `ai_sdk`) is the only implementation. `PhaseRunner` is the only place an LLM payload is built. A provider is one row in `provider_models.py` (OpenAI and Anthropic are native; the rest are OpenAI-compatible), its key and URL in `VercelAIConfig`, and its models in `model_catalog.py`. The model of each step is chosen by `AI_AGENT_MODEL_PHASE_<n>`, then `config/step_models.json`, then the profile, then the code default (a retired GitHub Models id).

## Consequences

- Positive: providers are swappable; one place to read a call.
- Negative: the code defaults are useless today; a real run always sets one of the first three.
