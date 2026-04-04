#import pytest
#from unittest.mock import Mock

import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
if project_root not in sys.path:
    sys.path.append(project_root)
    
from application.service.message_flow_service import MessageFlowService
from application.inbound.dto.message import TextRequestDTO
from domain.entities.response import Response
from domain.entities.payload import Payload

from application.outbound.ports.llm_ports import LLMOutboundPort
from infrastructure.outbound.llm.vercel import VercelAIAdapter, VercelAIConfig

def build_vercel_adapter() -> VercelAIAdapter:
    config = VercelAIConfig(
        #google_api_key=os.environ.get("GOOGLE_API_KEY", ""),
        github_api_key=os.environ.get("GITHUB_API_KEY", ""),
    )

    # 2. Create adapter and start session
    adapter = VercelAIAdapter(
        Config=config,
        SessionId="test-session-001",
    )
    adapter.start()

    return adapter

def test_message_service_text():
    vercel_adapter = build_vercel_adapter()
    service = MessageFlowService(vercel_adapter)

    request: TextRequestDTO = TextRequestDTO(
        session_id="test-session-001",
        #content="I need you to create a program for: Backendcode for go aws package",
        #content="sum 1+1",
        #content="create a python code to retrieve mails from google",
        content="Can you tell me how many years are in a millennium? and in a century?",
        metadata={"temperature": 1.0, "max_tokens": 10000},
        user_id="test-user-001",
    )

    response = service.text(request=request)
    print("Response:", response)

    
if __name__ == "__main__":
    test_message_service_text()
