from dataclasses import dataclass
from enum import Enum
from typing import get_args

from domain.value_objects.model_catalog import (  # noqa: F401  (re-exported for the callers)
    AnthropicModels,
    CohereModels,
    GithubModels,
    GoogleModels,
    GroqModels,
    MistralModels,
    ModelIdList,
    OllamaModels,
    OpenAIModels,
    SupportedModel,
)

ErrModelNotSupported = TypeError("Model not supported")

@dataclass(frozen=True)
class SelectedModel:
    """
    Value Object representing a single selected LLM model.

    Immutable.
    Comparable by value.
    Hashable.
    Provider-aware.
    """

    model: SupportedModel

    def __post_init__(self):
        if not isinstance(self.model, Enum):
            raise ErrModelNotSupported

    @property
    def id(self) -> str:
        """Returns the raw model string (for LangChain)."""
        return self.model.value

    @property
    def provider(self) -> str:
        """Returns provider name (OPENAI, GOOGLE, etc.)."""
        return self.model.__class__.__name__.replace("Models", "").upper()

    def is_openai(self) -> bool:
        return isinstance(self.model, ModelIdList.OPENAI)

    def is_google(self) -> bool:
        return isinstance(self.model, ModelIdList.GOOGLE)

    def is_anthropic(self) -> bool:
        return isinstance(self.model, ModelIdList.ANTHROPIC)

    def is_mistral(self) -> bool:  
        return isinstance(self.model, ModelIdList.MISTRAL)
    
    def is_groq(self) -> bool:
        return isinstance(self.model, ModelIdList.GROQ)
    
    def is_cohere(self) -> bool:
        return isinstance(self.model, ModelIdList.COHERE)
    
    def is_ollama(self) -> bool:
        return isinstance(self.model, ModelIdList.OLLAMA)
    
    def is_github(self) -> bool:
        return isinstance(self.model, ModelIdList.GITHUB)

    def is_local(self) -> bool:
        return isinstance(self.model, ModelIdList.OLLAMA)

    def __str__(self) -> str:
        return f"{self.provider}:{self.id}"
    
def get_selected_model(model_val: str) -> SelectedModel:
    """
    Scans through all Enum types defined in SupportedModel Union 
    to find a match for the provided string.
    """
    # get_args(SupportedModel) returns a tuple: 
    # (OpenAIModels, GoogleModels, AnthropicModels, ...)
    supported_enums = get_args(SupportedModel)

    for enum_cls in supported_enums:
        try:
            # Check if model_val exists in this specific Enum
            matched_member = enum_cls(model_val)
            return SelectedModel(model=matched_member)
        except ValueError:
            # Not in this Enum, move to the next one
            continue

    # If the loop finishes without a return
    raise  ErrModelNotSupported
