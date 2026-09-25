from abc import ABC, abstractmethod

from domain.entities.response import Response
from domain.entities.payload import Payload

class LLMOutboundPort(ABC):
    @abstractmethod
    def ask(self, Payload: Payload) -> Response | str:
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """True if a provider is configured well enough to attempt a call. No network call is made."""
        raise NotImplementedError