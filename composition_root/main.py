import os
import sys
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from shared_logging import TracingMiddleware, get_logger, init_logging

# -----------------------------------------------
#  PATH SETUP
# -----------------------------------------------

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Prompts, JSON schemas and MCP configs are opened with paths relative to the project root.
os.chdir(PROJECT_ROOT)

# Settings live in .env (never committed). Variables already set in the environment win.
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=False)

# -----------------------------------------------
#  OUTBOUND ADAPTERS
# -----------------------------------------------

from infrastructure.outbound.llm.config import VercelAIConfig
from infrastructure.outbound.llm.vercel import VercelAIAdapter
from infrastructure.outbound.mcp.client_manager import MCPClientManager
from infrastructure.outbound.mcp.config import load_supported_mcp_configs
from infrastructure.outbound.mcp.tool_executor import MCPToolExecutor
from infrastructure.outbound.usage.langfuse import LangfuseUsageReporter

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
        MCPToolExecutor + VercelAIAdapter (outbound) -> SessionService (application) -> SessionFastAPI (inbound)
    One session per user: every message is identified first and then answered by one flow (see
    application/orchestration/flows/router.py). Routes: /session/*, /health, /available.
    """

    init_logging("ai-agent")

    # Step 1: Outbound adapters — MCP tools and LLM provider
    mcpList = load_supported_mcp_configs()
    toolExecutor = MCPToolExecutor(MCPClientManager(mcpList))

    llmConfig = VercelAIConfig.from_env(tool_executor=toolExecutor)

    llmAdapter = VercelAIAdapter(Config=llmConfig)

    # Step 2: Application service — implements the inbound port
    usageReporter = LangfuseUsageReporter.from_env()        # None unless the LANGFUSE_* keys are set
    sessionService = SessionService(
        outbound_port=llmAdapter,
        mcp_list=mcpList,
        mcp_tools=toolExecutor,
        history_turns=int(os.environ.get("AI_AGENT_HISTORY_TURNS", "6")),
        usage_reporter=usageReporter,
    )

    # Step 3: FastAPI application
    app = FastAPI(
        title="AI Agent API",
        version="1.0.0",
        description=(
            "Hexagonal-architecture AI Agent service.\n\n"
            "## Session workflow\n"
            "1. **POST /session/start** — create a session\n"
            "2. **POST /session/message** — send messages within the session\n"
            "3. **POST /session/end** — terminate the session\n"
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Step 4: Inbound adapter
    SessionFastAPI(App=app, SessionPort=sessionService)
    app.add_middleware(TracingMiddleware)

    return app


# ===============================================
#  ENTRY POINT
# ===============================================

app = CreateApp()

if __name__ == "__main__":
    uvicorn.run(
        "composition_root.main:app",
        host=os.environ.get("AI_AGENT_HOST", "0.0.0.0"),
        port=int(os.environ.get("AI_AGENT_PORT", "7998")),
        reload=os.environ.get("AI_AGENT_RELOAD", "1") == "1",
        log_config=None,
    )
