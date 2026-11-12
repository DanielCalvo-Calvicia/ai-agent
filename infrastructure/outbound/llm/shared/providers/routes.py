# ===============================================
#  PROVIDER ROUTES
#  Which key and base URL serve a model. No SDK is imported here.
#  OpenAI and Anthropic are native (the key only). Every other provider is reached
#  through its OpenAI-compatible endpoint (base URL + key of the config).
# ===============================================

from typing import Callable, List, Optional, Tuple

from application.dtos.outbound.llm import SelectedModel
from infrastructure.outbound.llm.shared.providers.config import LLMConfig

ErrProviderNotSupported = ValueError(
    "The selected model provider is not supported by Vercel AI SDK."
)

# (does the route serve this model?, (api key, base url) taken from the config)
_Route = Tuple[Callable[[SelectedModel], bool], Callable[[LLMConfig], Tuple[str, str]]]

_OPENAI_COMPATIBLE_ROUTES: List[_Route] = [
    (lambda m: m.is_google(), lambda c: (c.google_api_key, c.google_url)),
    (lambda m: m.is_mistral(), lambda c: (c.mistral_api_key, c.mistral_url)),
    (lambda m: m.is_groq(), lambda c: (c.groq_api_key, c.groq_url)),
    (lambda m: m.is_cohere(), lambda c: (c.cohere_api_key, c.cohere_url)),
    (lambda m: m.is_ollama(), lambda c: ("ollama", c.OLLAMA_URL)),
]


def openai_compatible_credentials(model: SelectedModel, config: LLMConfig) -> Optional[Tuple[str, str]]:
    """The (api key, base url) of the OpenAI-compatible route that serves the model, or None when no route does."""
    for serves, credentials in _OPENAI_COMPATIBLE_ROUTES:
        if serves(model):
            return credentials(config)
    return None
