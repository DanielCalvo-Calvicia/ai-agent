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

from application.orchestration.flows.registry import FLOWS
from application.orchestration.flows.conversation_flow import CONVERSATION_FLOW
from application.service.session_service import SessionService

# -----------------------------------------------
#  INBOUND ADAPTERS
# -----------------------------------------------

from infrastructure.inbound.http.fastapi import SessionFastAPI, message_data_for


# ===============================================
#  COMPOSITION ROOT
# ===============================================

def CreateApp() -> FastAPI:
    """
    Wires all layers of the hexagonal architecture and returns
    the fully configured FastAPI application.

    Dependency graph, for every flow in the registry:
        MCPToolExecutor + VercelAIAdapter (outbound) -> SessionService (application) -> SessionFastAPI (inbound)
    Every flow has its own sessions and its own routes: /<flow-name>/session/*.
    """

    init_logging("ai-agent")

    # Step 1: Outbound adapters — MCP tools and LLM provider
    mcpList = load_supported_mcp_configs()
    toolExecutor = MCPToolExecutor(MCPClientManager(mcpList))

    llmConfig = VercelAIConfig.from_env(tool_executor=toolExecutor)

    llmAdapter = VercelAIAdapter(Config=llmConfig)

    # Step 2: Application services — one per flow, each implements the inbound port
    usageReporter = LangfuseUsageReporter.from_env()        # None unless the LANGFUSE_* keys are set
    sessionServices = {
        flow.name: SessionService(
            outbound_port=llmAdapter,
            mcp_list=mcpList,
            mcp_tools=toolExecutor,
            history_turns=int(os.environ.get("AI_AGENT_HISTORY_TURNS", "6")),
            usage_reporter=usageReporter,
            flow=flow,
        )
        for flow in FLOWS
    }

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

    # Step 4: Inbound adapters — each flow's routes wired to its own service
    for flowName, sessionService in sessionServices.items():
        SessionFastAPI(App=app, SessionPort=sessionService, prefix=f"/{flowName}", tag=flowName,
                       include_health=False, message_to_data=message_data_for(flowName))

    # The original /session/* routes, /health and /available stay as an alias of the conversation flow
    # until every caller (Brain) uses /conversation-flow/session/*.
    SessionFastAPI(App=app, SessionPort=sessionServices[CONVERSATION_FLOW.name], deprecated=True)
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
