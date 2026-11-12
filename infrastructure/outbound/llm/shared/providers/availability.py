# ===============================================
#  PROVIDER AVAILABILITY
#  Whether any provider is configured. No network call.
# ===============================================

from infrastructure.outbound.llm.shared.providers.config import LLMConfig


def any_provider_configured(config: LLMConfig) -> bool:
    """True when at least one provider is configured (a key, or Ollama's URL)."""
    return bool(
        config.openai_api_key or config.anthropic_api_key or config.google_api_key
        or config.mistral_api_key or config.groq_api_key or config.cohere_api_key
        or config.OLLAMA_URL
    )
