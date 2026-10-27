"""The JSON shape of every answer is the project contract ``ApiEnvelope``; ``data`` is the
endpoint's contract dataclass (``contracts.api.microservices.ai_agent``), matching every other
OBLIVION service.
"""

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse

from contracts.api.common.envelope import ApiEnvelope


def success(action: str, message: str, data: Any = None, *, ok: bool = True,
            code: int = status.HTTP_200_OK) -> JSONResponse:
    """``ok=False`` reports an error status for a request that was understood but not carried out.

    Both cases answer HTTP 200 (``code``): callers must read the envelope's ``status`` /
    ``data.success``, not the transport status code, for this family of outcomes.
    """
    envelope = ApiEnvelope.success(action, message, data, status_code=code) if ok \
        else ApiEnvelope.failure(action, message, code, data)
    return JSONResponse(status_code=code, content=envelope.to_dict())


def failure(action: str, message: str) -> JSONResponse:
    code = status.HTTP_500_INTERNAL_SERVER_ERROR
    return JSONResponse(status_code=code, content=ApiEnvelope.failure(action, message, code).to_dict())
