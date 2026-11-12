# ===============================================
#  VERCEL OPTIONS
#  The keyword arguments of ai_sdk.generate_text besides the model and the messages.
# ===============================================

from typing import Any, Dict

from application.dtos.outbound.llm import Payload
from infrastructure.outbound.llm.shared.providers.config import LLMConfig
from infrastructure.outbound.llm.shared.schemas.anthropic_schema import anthropic_response_format
from infrastructure.outbound.llm.vercel.tool_adapter import resolve_tools


def build_options(config: LLMConfig, payload: Payload) -> Dict[str, Any]:
    options: Dict[str, Any] = {}

    if payload.seed is not None:
        options["seed"] = payload.seed

    if payload.response_format:
        response_format = payload.response_format.to_dict()
        # Anthropic's endpoint needs "strict": true and a schema in the subset its structured outputs accept.
        options["response_format"] = anthropic_response_format(response_format) if payload.model.is_anthropic() else response_format

    tools = resolve_tools(config, payload.tools)
    if tools:
        options["tools"] = tools

    return options
