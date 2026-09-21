# ===============================================
#  VERCEL AI ADAPTER
#  Implements LLMOutboundPort with the Python AI SDK.
#  Provider mapping: provider_models.py. Tools: tools.py.
#  Answer parsing: response_mapper.py. Settings: config.py.
# ===============================================

import json
from typing import Any, Dict, List

from ai_sdk import generate_text
from ai_sdk.types import CoreSystemMessage, CoreUserMessage

from application.outbound.ports.llm_ports import LLMOutboundPort
from domain.entities.payload import Payload
from domain.entities.response import Response
from infrastructure.outbound.llm.config import VercelAIConfig
from infrastructure.outbound.llm.provider_models import create_model
from infrastructure.outbound.llm.response_mapper import build_response
from infrastructure.outbound.llm.tools import resolve_tools
from shared_logging import get_logger

logger = get_logger(__name__)


class VercelAIAdapter(LLMOutboundPort):
    """One stateless LLM call per `ask`: system prompt + user message in, a domain Response out."""

    def __init__(self, Config: VercelAIConfig):
        self.config = Config

    def ask(self, Payload: Payload) -> Response:
        model = create_model(self.config, Payload)

        try:
            result = generate_text(
                model=model,
                messages=_build_messages(Payload),
                **_build_options(self.config, Payload),
            )

            tokens_usage = result.usage.model_dump() if result.usage else {}

            if not Payload.response_format:
                return build_response(result.text, tokens_usage)

            return build_response(json.loads(result.text), tokens_usage)

        except Exception:
            logger.exception("Vercel AI SDK error")
            raise


def _build_messages(payload: Payload) -> List[Any]:
    messages: List[Any] = []

    if payload.system_prompt:
        messages.append(CoreSystemMessage(content=payload.system_prompt.content))

    messages.append(CoreUserMessage(content=payload.message.content))

    return messages


def _build_options(config: VercelAIConfig, payload: Payload) -> Dict[str, Any]:
    """The keyword arguments of generate_text besides the model and the messages."""
    options: Dict[str, Any] = {}

    if payload.seed is not None:
        options["seed"] = payload.seed

    if payload.response_format:
        options["response_format"] = payload.response_format.to_dict()

    tools = resolve_tools(config, payload.tools)
    if tools:
        options["tools"] = tools

    return options
