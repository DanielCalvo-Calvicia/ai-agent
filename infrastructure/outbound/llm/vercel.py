#------------------------------------------------
#  NATIVE
# -----------------------------------------------

from typing import AsyncGenerator, AsyncIterator, Callable, Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import uuid
import json
import os

# -----------------------------------------------
#  DOMAIN
# -----------------------------------------------

from domain.entities.action import Action, create_action
from domain.entities.payload import Payload
from domain.entities.response import Response, _build_response
from domain.value_objects.constraints.constraints import Constraints, get_format_from_string, get_language_from_string, get_tone_from_string
from domain.value_objects.mcp_context import McpContext
from domain.value_objects.mcp_routing.mcp_routing import MCPRouting
from domain.value_objects.message import Message, Role
from domain.value_objects.model import SelectedModel
from domain.value_objects.next_step.next_step import NextStep, create_next_step
from domain.value_objects.safety_and_validation.safety_and_validation import SafetyAndValidation, create_safety_and_validation
from domain.value_objects.task_category.task_category import TaskCategory, create_task_category
from domain.value_objects.user_goal.user_goal import UserGoal, create_user_goal
from domain.value_objects.missing_information.missing_information import MissingInformation, create_missing_information

# -----------------------------------------------
#  APPLICATION
# -----------------------------------------------
from application.outbound.ports.llm_ports import LLMOutboundPort



# -----------------------------------------------
#  VERCEL
# -----------------------------------------------

from ai_sdk import generate_text, stream_text
from ai_sdk.generate_text import GenerateTextResult
from ai_sdk import openai as openai_provider
from ai_sdk import anthropic as anthropic_provider
from ai_sdk.providers.anthropic import AnthropicModel as OpenAICompatibleModel
from ai_sdk.types import CoreSystemMessage, CoreUserMessage, CoreAssistantMessage




# -----------------------------------------------
#  CONFIGURATION
# -----------------------------------------------

@dataclass(frozen=True)
class VercelAIConfig:
    """Immutable configuration for the Vercel AI SDK adapter."""

    openai_api_key: str = os.environ.get('OPRENAI_API_KEY', "")
    anthropic_api_key: str = os.environ.get('ANTHROPIC_API_KEY', "")
    google_api_key: str = os.environ.get('GOOGLE_API_KEY', "")
    mistral_api_key: str = os.environ.get('MISTRAL_API_KEY', "")
    groq_api_key: str = os.environ.get('GROQ_API_KEY', "")
    cohere_api_key: str = os.environ.get('COHERE_API_KEY', "")
    OLLAMA_URL: str = os.environ.get('OLLAMA_URL', "")
    github_api_key: str = os.environ.get('GITHUB_API_KEY', "")


# -----------------------------------------------
#  PROVIDER ENDPOINTS (OpenAI-compatible)
# -----------------------------------------------

PROVIDER_BASE_URLS: Dict[str, str] = {
    "GOOGLE": os.environ.get('GOOGLE_URL', ""),
    "MISTRAL": os.environ.get('MISTRAL_URL', ""),
    "GROQ": os.environ.get('GROQ_URL', ""),
    "COHERE": os.environ.get('COHERE_URL', ""),
    "GITHUB": os.environ.get('GITHUB_URL', ""),
}


# -----------------------------------------------
#  ROLE MAPPING
# -----------------------------------------------

ROLE_TO_VERCEL: Dict[Role, type] = {
    Role.SYSTEM: CoreSystemMessage,
    Role.USER: CoreUserMessage,
    Role.ASSISTANT: CoreAssistantMessage,
}


# -----------------------------------------------
#  ERRORS
# -----------------------------------------------

ErrSessionNotStarted = RuntimeError("Vercel AI session has not been started.")
ErrProviderNotSupported = ValueError(
    "The selected model provider is not supported by Vercel AI SDK."
)
ErrStreamingNotAvailable = RuntimeError(
    "Streaming is not available for this provider."
)
ErrAudioNotSupported = RuntimeError(
    "Audio streaming is not supported by the Python AI SDK."
)

ErrResponseNotSpecified = RuntimeError(
    "No response format specified"
)


# -----------------------------------------------
#  ADAPTER
# -----------------------------------------------

class VercelAIAdapter(LLMOutboundPort):
    """
    Session-scoped outbound adapter that uses the Python AI SDK
    (Vercel AI SDK port) for unified multi-provider LLM access.

    Supports:
      - Synchronous completion  (ask)
      - Streaming text          (stream_text)
      - Conversation history    (append_message / get_history)
      - Provider-agnostic model resolution
        (OpenAI, Anthropic, Google, Mistral, Groq, Cohere, Ollama)

    All providers are accessed through a single adapter by leveraging
    the AI SDK's provider-agnostic functions.  OpenAI and Anthropic
    use their native SDK providers; every other provider is reached
    through its OpenAI-compatible endpoint.
    """

    config: VercelAIConfig
    session_id: str
    _current_model: Optional[SelectedModel]
    _history: List[Any]
    _started: bool
    _created_at: str

    def __init__(
        self,
        Config: VercelAIConfig,
        SessionId: Optional[str] = None,
    ):
        self.config = Config
        self.session_id = SessionId or str(uuid.uuid4())
        self._current_model = None
        self._history = []
        self._started = False
        self._created_at = datetime.now(timezone.utc).isoformat()

    # -----------------------------------------------
    #  LIFECYCLE
    # -----------------------------------------------

    def start(self) -> None:
        """Initialise the Vercel AI SDK adapter session."""
        self._started = True

    def stop(self) -> None:
        """Tear down the session and clear state."""
        self._current_model = None
        self._history.clear()
        self._started = False

    def is_active(self) -> bool:
        return self._started

    # -----------------------------------------------
    #  MODEL RESOLUTION
    # -----------------------------------------------

    def set_model(self, Model: SelectedModel) -> None:
        """Store the selected model for subsequent calls."""
        self._assert_started()
        self._current_model = Model

    # -----------------------------------------------
    #  CORE — ask  (LLMOutboundPort)
    # -----------------------------------------------

    def ask(self, Payload: Payload) -> Response:
        self._assert_started()

        model = _create_model(self.config, Payload)

        ask_kwargs = _create_input_args(Payload)

        messages: List[Any] = []#self._build_messages()

        if Payload.system_prompt:
            system_prompt: CoreSystemMessage = CoreSystemMessage(
                content=Payload.system_prompt.content
            )
            messages.append(system_prompt)

        new_message = CoreUserMessage(content=Payload.message.content)
        messages.append(new_message)

        # 3. Invoke the model
        try:
            result = generate_text(
                model=model,
                messages=messages,
                **ask_kwargs,
            )

            tokens_usage = {}
            if (result.usage):
                tokens_usage = result.usage.model_dump()

            if not Payload.response_format:
                return _build_response(result.text, tokens_usage)
            
            responseData = json.loads(result.text)
            self._history.append(
                CoreAssistantMessage(content=json.dumps(responseData))
            )
            
            return _build_response(responseData, tokens_usage)

        except Exception as e:
            print(f"Vercel AI SDK error: {e}")
            raise e

    # -----------------------------------------------
    #  STREAMING — text
    # -----------------------------------------------

    async def stream_text(
        self,
        Payload: Payload,
        OnChunk: Optional[Callable[[str], Any]] = None,
    ) -> AsyncGenerator[Any, Any]:
        """
        Yields text chunks as they arrive from the LLM.

        Optionally calls *OnChunk* with each fragment (useful for
        WebSocket / SSE forwarding).
        """
        self._assert_started()

        
        model = _create_model(self.config, Payload)

        messages = self._build_messages()

        new_message = CoreUserMessage(content=Payload.message.content)
        messages.append(new_message)

        fullContent = ""
        streamResult = stream_text(
            model=model,
            messages=messages,
        )

        async for chunk in streamResult.text_stream:
            fullContent += chunk

            if OnChunk:
                OnChunk(chunk)

            yield chunk

        self._history.append(CoreAssistantMessage(content=fullContent))

    # -----------------------------------------------
    #  STREAMING — audio
    # -----------------------------------------------

    async def stream_audio(
        self,
        Payload: Payload,
        AudioFormat: str = "pcm16",
        SampleRate: int = 24000,
        OnAudioChunk: Optional[Callable[[bytes, Optional[str]], Any]] = None,
    ) -> AsyncIterator[dict]:
        """
        Audio streaming is not supported by the Python AI SDK.
        Raises ErrAudioNotSupported.
        """
        raise ErrAudioNotSupported

    # -----------------------------------------------
    #  CONVERSATION HISTORY
    # -----------------------------------------------

    def append_message(self, MessageRole: Role, Content: str) -> None:
        """Manually push a message onto the session history."""
        messageClass = ROLE_TO_VERCEL.get(MessageRole, CoreUserMessage)
        self._history.append(messageClass(content=Content))

    def get_history(self) -> List[Any]:
        """Return the full conversation history for this session."""
        return list(self._history)

    def clear_history(self) -> None:
        self._history.clear()

    # -----------------------------------------------
    #  SESSION METADATA
    # -----------------------------------------------

    def get_session_metadata(self) -> dict:
        """Return metadata dict suitable for logging or tracking."""
        return {
            "session_id": self.session_id,
            "created_at": self._created_at,
            "adapter": "vercel_ai_sdk",
        }

    # -----------------------------------------------
    #  PRIVATE HELPERS
    # -----------------------------------------------

    def _assert_started(self) -> None:
        if not self._started:
            raise ErrSessionNotStarted

    def _build_messages(
        self,
    ) -> List[Any]:
        """
        Convert domain Payload into AI SDK message list,
        prepending session history and optional system instruction.
        """
        history = self._history

        return history


# -----------------------------------------------
#  MODULE-LEVEL HELPERS (PRIVATE)
# -----------------------------------------------

def _create_model(
    Config: VercelAIConfig,
    Payload: Payload,
):
    model_kwargs: Dict[str, Any] = {}        

    if Payload.temperature is not None:
        model_kwargs["temperature"] = Payload.temperature.value
    if Payload.max_tokens is not None:
        model_kwargs["max_tokens"] = Payload.max_tokens.value
    if Payload.top_p is not None:
        model_kwargs["top_p"] = Payload.top_p.value
    
    model = _resolve_provider_model(
        Payload.model,
        Config,
        model_kwargs,
    )

    return model

def _resolve_provider_model(
    Model: SelectedModel,
    Config: VercelAIConfig,
    kwargs: Dict[str, Any],
) -> Any:
    """
    Map a domain SelectedModel to a Python AI SDK provider model.

    Uses native providers for OpenAI and Anthropic.
    Uses OpenAI-compatible endpoints for Google, Mistral, Groq,
    Cohere, and Ollama.

    Raises ErrProviderNotSupported for unknown providers.
    """
    modelId = Model.id

    # --- Native OpenAI ---
    if Model.is_openai():
        return openai_provider(
            modelId,
            api_key=Config.openai_api_key,
            **kwargs,
        )

    # --- Native Anthropic ---
    if Model.is_anthropic():
        return anthropic_provider(
            modelId,
            api_key=Config.anthropic_api_key,
            **kwargs,
        )

    # --- Google via OpenAI-compatible endpoint ---
    if Model.is_google():
        return OpenAICompatibleModel(
            modelId,
            api_key=Config.google_api_key,
            base_url=PROVIDER_BASE_URLS["GOOGLE"],
            **kwargs,
        )

    # --- Mistral via OpenAI-compatible endpoint ---
    if Model.is_mistral():
        return OpenAICompatibleModel(
            modelId,
            api_key=Config.mistral_api_key,
            base_url=PROVIDER_BASE_URLS["MISTRAL"],
            **kwargs,
        )

    # --- Groq via OpenAI-compatible endpoint ---
    if Model.is_groq():
        return OpenAICompatibleModel(
            modelId,
            api_key=Config.groq_api_key,
            base_url=PROVIDER_BASE_URLS["GROQ"],
            **kwargs,
        )

    # --- Cohere via OpenAI-compatible endpoint ---
    if Model.is_cohere():
        return OpenAICompatibleModel(
            modelId,
            api_key=Config.cohere_api_key,
            base_url=PROVIDER_BASE_URLS["COHERE"],
            **kwargs,
        )
    
    # --- Ollama via OpenAI-compatible endpoint ---
    if Model.is_ollama():
        return OpenAICompatibleModel(
            modelId,
            api_key="ollama",
            base_url=PROVIDER_BASE_URLS["OLLAMA_URL"],
            **kwargs,
        )
    
    # --- GitHub via OpenAI-compatible endpoint ---
    if Model.provider == "GITHUB":
        return OpenAICompatibleModel(
            modelId,
            api_key=Config.github_api_key,
            base_url=PROVIDER_BASE_URLS["GITHUB"],
            **kwargs,
        )

    # --- Ollama via OpenAI-compatible endpoint ---
    if Model.is_local():
        return OpenAICompatibleModel(
            modelId,
            api_key="ollama",
            base_url=PROVIDER_BASE_URLS["OLLAMA_URL"],
            **kwargs,
        )

    raise ErrProviderNotSupported

def _create_input_args(Payload: Payload) -> Dict[str, Any]:
    ask_kwargs: Dict[str, Any] = {}

    if Payload.seed is not None:
        ask_kwargs["seed"] = Payload.seed

    #if Payload.system_prompt:
    #    ask_kwargs["system_prompt"] = Payload.system_prompt.content

    if Payload.response_format:
        ask_kwargs["response_format"] = Payload.response_format.to_dict()

    return ask_kwargs



def _supports_native_audio(Model: SelectedModel) -> bool:
    """
    Return True if the model supports native audio streaming.
    Currently not supported in the Python AI SDK.
    """
    return False
