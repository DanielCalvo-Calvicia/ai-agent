from dataclasses import dataclass

from domain.entities.payload import Payload
from domain.entities.response import Response

class Conversation:
    id: int
    payload: Payload
    response: Response

    def __init__(self, id: int, payload: Payload, response: Response) -> None:
        self.id = id
        self.payload = payload
        self.response = response
