# ===============================================
#  VERCEL AI ADAPTER
#  Implements LLMOutboundPort with the Python AI SDK.
#  Model objects: models.py. Messages: messages.py. Options: options.py. Tools: tool_adapter.py.
#  Answer parsing: application/mappers/outbound/response_mapper.py.
#  Settings and providers: shared/providers/. The schema sent to Claude models: shared/schemas/.
# ===============================================

import json

from ai_sdk import generate_text

from application.ports.outbound.llm_ports import LLMOutboundPort
from application.dtos.outbound.llm import Payload, Response
from application.mappers.outbound.response_mapper import build_response
from infrastructure.outbound.llm.shared.providers.availability import any_provider_configured
from infrastructure.outbound.llm.shared.providers.config import LLMConfig
from infrastructure.outbound.llm.vercel.messages import build_messages
from infrastructure.outbound.llm.vercel.models import create_model
from infrastructure.outbound.llm.vercel.options import build_options
from shared_logging import get_logger

logger = get_logger(__name__)


class VercelAIAdapter(LLMOutboundPort):
    """One stateless LLM call per `ask`: system prompt + user message in, a domain Response out."""

    def __init__(self, Config: LLMConfig):
        self.config = Config

    def ask(self, Payload: Payload) -> Response:
        model = create_model(self.config, Payload)

        try:
            result = generate_text(
                model=model,
                messages=build_messages(Payload),
                **build_options(self.config, Payload),
            )

            tokens_usage = result.usage.model_dump() if result.usage else {}

            if not Payload.response_format:
                return build_response(result.text, tokens_usage)

            return build_response(json.loads(result.text), tokens_usage)

        except Exception:
            logger.exception("Vercel AI SDK error")
            raise

    def is_available(self) -> bool:
        """True when at least one provider is configured (a key, or Ollama's URL). No network call."""
        return any_provider_configured(self.config)
