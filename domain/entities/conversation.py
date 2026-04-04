from dataclasses import dataclass
from typing import Optional
import uuid

from domain.entities.payload import Payload
from domain.entities.response import Response

class Conversation:
    id: str
    request: str
    response: Optional[str]

    def __init__(self, id: str, request: str, response: Optional[str]) -> None:
        self.id = id
        self.request = request
        self.response = response
