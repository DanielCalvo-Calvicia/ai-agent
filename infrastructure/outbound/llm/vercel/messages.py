# ===============================================
#  VERCEL MESSAGES
#  The ai_sdk messages of a payload.
# ===============================================

from typing import Any, List

from ai_sdk.types import CoreSystemMessage, CoreUserMessage

from application.dtos.outbound.llm import Payload


def build_messages(payload: Payload) -> List[Any]:
    messages: List[Any] = []

    if payload.system_prompt:
        messages.append(CoreSystemMessage(content=payload.system_prompt.content))

    messages.append(CoreUserMessage(content=payload.message.content))

    return messages
