"""
MANUAL script: sends one message through the whole agent with the REAL LLM.
It costs money and needs the keys of .env. Run it from the ai-agent folder:
    python tests/manual/full_flow_real_llm.py   (with the venv python)
Not collected by pytest.
"""
import os
import sys

from dotenv import load_dotenv

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.append(project_root)
sys.path.append(os.path.join(project_root, "tests"))
os.chdir(project_root)
load_dotenv(os.path.join(project_root, ".env"), override=False)
    
from composition_root.environment import install_environment
install_environment()          # the application reads no file and no environment variable itself: it is given them
from application.service.message_flow_service import MessageFlowService
from application.dtos.inbound.message import TextRequestDTO
from domain.entities.llm_response.response import Response
from domain.entities.llm_request.payload import Payload

from application.ports.outbound.llm_ports import LLMOutboundPort
from infrastructure.outbound.llm.shared.providers.config import LLMConfig
from infrastructure.outbound.llm.vercel.adapter import VercelAIAdapter
from model_table import manual_service

def build_vercel_adapter() -> VercelAIAdapter:
    config = LLMConfig.from_env()

    return VercelAIAdapter(Config=config)

def run_message_service_text():
    vercel_adapter = build_vercel_adapter()
    service = MessageFlowService(vercel_adapter, **manual_service())        # a service runs a profile since T-05.7

    request: TextRequestDTO = TextRequestDTO(
        session_id="test-session-001",
        #content="I need you to create a program for: Backendcode for go aws package",
        #content="sum 1+1",
        #content="create a python code to retrieve mails from google",
        content="Write a file on a directory with the text inside \"text\" and return the directory where you write it",
        metadata={"temperature": 1.0, "max_tokens": 10000},
        user_id="test-user-001",
    )

    response = service.text(request=request)
    print("Response:", response)

    
if __name__ == "__main__":
    run_message_service_text()
