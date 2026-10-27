from abc import ABC, abstractmethod
from typing import Optional
from application.inbound.dto.message import TextRequestDTO, TextResponseDTO
from application.outbound.ports.llm_ports import LLMOutboundPort

class MessageInboundPort(ABC):
    def __init__(self, outbound_port: LLMOutboundPort, mcp_list: list, history: Optional[list] = None, mcp_tools=None, paused=None) -> None:
        raise NotImplementedError
    
    @abstractmethod
    def text(self, request: TextRequestDTO) -> TextResponseDTO:
        raise NotImplementedError