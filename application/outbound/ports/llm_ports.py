from abc import ABC, abstractmethod

from domain.entities.response import Response
from domain.entities.payload import Payload

class LLMOutboundPort(ABC):
    @abstractmethod
    def ask(self, Payload: Payload) -> Response | str:
        raise NotImplementedError