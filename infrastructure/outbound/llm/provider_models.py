# ===============================================
#  PROVIDER MODELS
#  Maps a domain model to an ai_sdk model object.
#  OpenAI and Anthropic are native. Every other provider is reached
#  through its OpenAI-compatible endpoint (base URL + key of the config).
#  ai_sdk's AnthropicModel is an OpenAI-client provider with a base_url,
#  which is why it serves all of them.
# ===============================================

from typing import Any, Callable, Dict, List, Tuple

from ai_sdk import anthropic as anthropic_provider
from ai_sdk import openai as openai_provider
from ai_sdk.providers.anthropic import AnthropicModel as OpenAICompatibleModel

from domain.entities.llm_request.payload import Payload
from domain.value_objects.llm_request.model import SelectedModel
from infrastructure.outbound.llm.config import VercelAIConfig

ErrProviderNotSupported = ValueError(
    "The selected model provider is not supported by Vercel AI SDK."
)

# (does the route serve this model?, (api key, base url) taken from the config)
_Route = Tuple[Callable[[SelectedModel], bool], Callable[[VercelAIConfig], Tuple[str, str]]]

_OPENAI_COMPATIBLE_ROUTES: List[_Route] = [
    (lambda m: m.is_google(), lambda c: (c.google_api_key, c.google_url)),
    (lambda m: m.is_mistral(), lambda c: (c.mistral_api_key, c.mistral_url)),
    (lambda m: m.is_groq(), lambda c: (c.groq_api_key, c.groq_url)),
    (lambda m: m.is_cohere(), lambda c: (c.cohere_api_key, c.cohere_url)),
    (lambda m: m.is_ollama(), lambda c: ("ollama", c.OLLAMA_URL)),
    (lambda m: m.is_github(), lambda c: (c.github_api_key, c.github_url)),
]


def create_model(config: VercelAIConfig, payload: Payload) -> Any:
    """The ai_sdk model for the payload, with its sampling options (temperature, max tokens, top_p)."""
    options: Dict[str, Any] = {}

    if payload.temperature is not None:
        options["temperature"] = payload.temperature.value
    if payload.max_tokens is not None:
        options["max_tokens"] = payload.max_tokens.value
    if payload.top_p is not None:
        options["top_p"] = payload.top_p.value

    return resolve_provider_model(payload.model, config, options)


def resolve_provider_model(model: SelectedModel, config: VercelAIConfig, options: Dict[str, Any]) -> Any:
    """Raises ErrProviderNotSupported for a provider without a route."""
    if model.is_openai():
        return openai_provider(model.id, api_key=config.openai_api_key, **options)

    if model.is_anthropic():
        return anthropic_provider(model.id, api_key=config.anthropic_api_key, **options)

    for serves, credentials in _OPENAI_COMPATIBLE_ROUTES:
        if serves(model):
            api_key, base_url = credentials(config)
            return OpenAICompatibleModel(model.id, api_key=api_key, base_url=base_url, **options)

    raise ErrProviderNotSupported
