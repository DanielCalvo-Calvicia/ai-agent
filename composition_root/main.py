import os
import sys
import uvicorn
from fastapi import FastAPI

# -----------------------------------------------
#  PATH SETUP
# -----------------------------------------------

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# -----------------------------------------------
#  OUTBOUND ADAPTERS
# -----------------------------------------------

from infrastructure.outbound.llm.vercel import VercelAIAdapter, VercelAIConfig

# -----------------------------------------------
#  APPLICATION SERVICES
# -----------------------------------------------

from application.service.session_service import SessionService

# -----------------------------------------------
#  INBOUND ADAPTERS
# -----------------------------------------------

from infrastructure.inbound.http.fastapi import SessionFastAPI


# ===============================================
#  COMPOSITION ROOT
# ===============================================

def CreateApp() -> FastAPI:
    """
    Wires all layers of the hexagonal architecture and returns
    the fully configured FastAPI application.

    Dependency graph:
        VercelAIAdapter (outbound) -> SessionService (application) -> SessionFastAPI (inbound)
    """

    # Step 1: Outbound adapter — LLM provider
    llmConfig = VercelAIConfig(
        github_api_key=os.environ.get("GITHUB_API_KEY", ""),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        google_api_key=os.environ.get("GOOGLE_API_KEY", ""),
    )

    llmAdapter = VercelAIAdapter(Config=llmConfig)
    llmAdapter.start()

    # Step 2: Application service — implements the inbound port
    sessionService = SessionService(outbound_port=llmAdapter)

    # Step 3: FastAPI application
    app = FastAPI(
        title="AI Agent API",
        version="1.0.0",
    )

    # Step 4: Inbound adapter — HTTP routes wired to the service
    SessionFastAPI(App=app, SessionPort=sessionService)

    return app


# ===============================================
#  ENTRY POINT
# ===============================================

app = CreateApp()

if __name__ == "__main__":
    uvicorn.run(
        "composition_root.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
