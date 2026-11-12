from abc import ABC, abstractmethod

from application.dtos.inbound.message import TextRequestDTO, TextResponseDTO


class MessageInboundPort(ABC):
    @abstractmethod
    def text(self, request: TextRequestDTO) -> TextResponseDTO:
        raise NotImplementedError