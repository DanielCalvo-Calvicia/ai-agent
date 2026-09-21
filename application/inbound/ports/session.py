from abc import ABC, abstractmethod

from application.inbound.dto.session import (
    StartSessionRequestDTO, 
    StartSessionResponseDTO,
    EndSessionRequestDTO, 
    EndSessionResponseDTO,
    MessageReceivedRequestDTO, 
    MessageReceivedResponseDTO
)

class SessionInboundPort(ABC):
    @abstractmethod
    def start_session(self, request: StartSessionRequestDTO) -> StartSessionResponseDTO:
        raise NotImplementedError

    @abstractmethod
    def end_session(self, request: EndSessionRequestDTO) -> EndSessionResponseDTO:
        raise NotImplementedError

    @abstractmethod
    def message_received(self, request: MessageReceivedRequestDTO) -> MessageReceivedResponseDTO:
        raise NotImplementedError

