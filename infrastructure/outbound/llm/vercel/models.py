# ===============================================
#  VERCEL MODELS
#  Maps a domain model to an ai_sdk model object.
#  Which key and URL serve a model: shared/providers/routes.py.
#  ai_sdk's AnthropicModel is an OpenAI-client provider with a base_url,
#  which is why it serves every OpenAI-compatible provider.
# ===============================================

from typing import Any, Dict

from ai_sdk import anthropic as anthropic_provider
from ai_sdk import openai as openai_provider
from ai_sdk.providers.anthropic import AnthropicModel as OpenAICompatibleModel

from application.dtos.outbound.llm import Payload, SelectedModel
from infrastructure.outbound.llm.shared.providers.config import LLMConfig
from infrastructure.outbound.llm.shared.providers.routes import ErrProviderNotSupported, openai_compatible_credentials


def create_model(config: LLMConfig, payload: Payload) -> Any:
    """The ai_sdk model for the payload, with its sampling options (temperature, max tokens, top_p)."""
    options: Dict[str, Any] = {}

    if payload.temperature is not None:
        options["temperature"] = payload.temperature.value
    if payload.max_tokens is not None:
        options["max_tokens"] = payload.max_tokens.value
    if payload.top_p is not None:
        options["top_p"] = payload.top_p.value

    return resolve_provider_model(payload.model, config, options)


def resolve_provider_model(model: SelectedModel, config: LLMConfig, options: Dict[str, Any]) -> Any:
    """Raises ErrProviderNotSupported for a provider without a route."""
    if model.is_openai():
        return openai_provider(model.id, api_key=config.openai_api_key, **options)

    if model.is_anthropic():
        return anthropic_provider(model.id, api_key=config.anthropic_api_key, **options)

    credentials = openai_compatible_credentials(model, config)
    if credentials is None:
        raise ErrProviderNotSupported

    api_key, base_url = credentials
    return OpenAICompatibleModel(model.id, api_key=api_key, base_url=base_url, **options)
