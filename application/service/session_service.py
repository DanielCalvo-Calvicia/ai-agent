
# ===============================================
#  IMPORTS
# ===============================================

# -----------------------------------------------
#  NATIVE
# -----------------------------------------------

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type


# -----------------------------------------------
#  PORTS
# -----------------------------------------------

from application.inbound.ports.session import SessionInboundPort
from application.inbound.ports.message_flow_ports import MessageInboundPort
from application.outbound.ports.llm_ports import LLMOutboundPort

# -----------------------------------------------
#  SERIVCES
# -----------------------------------------------

from application.service.message_flow_service import MessageFlowService

# -----------------------------------------------
#  DOMAIN
# -----------------------------------------------

from domain.entities.conversation_history import ConversationHistory
from domain.entities.conversation import Conversation
from domain.entities.session import Session

# -----------------------------------------------
#  DTOS
# -----------------------------------------------
from application.inbound.dto.session import (
    StartSessionRequestDTO, 
    StartSessionResponseDTO,
    EndSessionRequestDTO, 
    EndSessionResponseDTO,
    MessageReceivedRequestDTO, 
    MessageReceivedResponseDTO
)

from application.inbound.dto.message import TextRequestDTO, TextResponseDTO

# ===============================================
#  TRACKING
# ===============================================



# ===============================================
#  OBJECTS
# ===============================================

class ConversationFlowItem:
    conversation: Conversation
    message_flow_service: MessageInboundPort

    def __init__(self, conversation: Conversation, message_flow_service: MessageInboundPort) -> None:
        self.conversation = conversation
        self.message_flow_service = message_flow_service

class ConversationFlow:
    conversation_flow_items: Dict[str, ConversationFlowItem]

    def __init__(self) -> None:
        self.conversation_flow_items = {}

    def add_conversation_flow_item(self, id: str, conversation_flow_item: ConversationFlowItem) -> None:
        self.conversation_flow_items[id] = conversation_flow_item

class UserSession:
    session_id: str
    conversation_flow: Optional[ConversationFlow]
    username: str
    email: Optional[str] = None

    def __init__(self, session_id: str, username: str, email: Optional[str] = None, conversation_flow: Optional[ConversationFlow] = None) -> None:
        self.session_id = session_id
        self.username = username
        self.email = email
        self.conversation_flow = conversation_flow

# ===============================================
#  SERVICE
# ===============================================

class SessionService(SessionInboundPort):
    sessions: Dict[str, UserSession] = field(default_factory=dict)

    llm_adapter: LLMOutboundPort
    message_service_type: type[MessageInboundPort]
    
    def __init__(self, outbound_port: LLMOutboundPort, message_service_type: type[MessageInboundPort] = MessageFlowService) -> None:
        self.llm_adapter = outbound_port
        self.message_service_type = message_service_type

    def start_session(self, request: StartSessionRequestDTO) -> StartSessionResponseDTO:
        try:
            session_id = str(uuid.uuid4())

            userSession: UserSession = UserSession(
                username=request.username, 
                email=request.email, 
                session_id=session_id
            )

            self.sessions[session_id] = userSession

            return StartSessionResponseDTO(
                session_id=session_id,
                message="Session started successfully.",
                success=True
            )
        except Exception as e:
            return StartSessionResponseDTO(
                session_id="",
                message=f"Failed to start session: {str(e)}",
                success=False
            )
        
    def end_session(self, request: EndSessionRequestDTO) -> EndSessionResponseDTO:       
        try:
            if request.session_id in self.sessions:
                del self.sessions[request.session_id]
                return EndSessionResponseDTO(
                    success=True,
                    message="Session ended successfully."
                )
            else:
                return EndSessionResponseDTO(
                    success=False,
                    message="Session ID not found."
                )
        except Exception as e:
            return EndSessionResponseDTO(
                success=False,
                message=f"Failed to end session: {str(e)}"
            )
    
    def message_received(self, request: MessageReceivedRequestDTO) -> MessageReceivedResponseDTO:
        try:
            if request.session_id not in self.sessions:
                return MessageReceivedResponseDTO(
                    response="Session ID not found.",
                    success=False
                )
            
            if (self.sessions[request.session_id] is None):
                return MessageReceivedResponseDTO(
                    response="Session is not active.",
                    success=False
                )
            
            new_conversation_flow_item: ConversationFlowItem = self.get_new_conversation_flow_item(request.message)
            
            testRequestDTO: TextRequestDTO = TextRequestDTO(
                request_id = request.request_id,
                user_id = request.user_id,
                correlation_id = request.correlation_id,
                metadata = request.metadata,
                timestamp = request.timestamp,
                session_id = request.session_id,
                content = request.message
            )
            
            conversation_response: TextResponseDTO = new_conversation_flow_item.message_flow_service.text(testRequestDTO)
            new_conversation_flow_item.conversation.response = conversation_response.content

            self.add_conversation_flow_item_to_session(request.session_id, new_conversation_flow_item)

            return MessageReceivedResponseDTO(
                response=new_conversation_flow_item.conversation.response,
                success=True
            )
        except Exception as e:
            return MessageReceivedResponseDTO(
                response=f"Failed to process message: {str(e)}",
                success=False
            )
        
    def get_new_conversation_flow_item(self, message: str) -> ConversationFlowItem:
        
        messageFlow: MessageInboundPort = self.message_service_type(
            outbound_port=self.llm_adapter,
            mcp_list=[]
        )
        
        conversation = Conversation(
            id=str(uuid.uuid4()),
            request=message,
            response=None
        )

        conversation_flow_item = ConversationFlowItem(
            conversation,
            messageFlow
        )

        return conversation_flow_item   
    
    def add_conversation_flow_item_to_session(self, session_id: str, conversation_flow_item: ConversationFlowItem) -> None:
        if session_id in self.sessions:
            user_session = self.sessions[session_id]
            if user_session.conversation_flow is None:
                user_session.conversation_flow = ConversationFlow()
            user_session.conversation_flow.add_conversation_flow_item(conversation_flow_item.conversation.id, conversation_flow_item)
