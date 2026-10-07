import os
import sys
import asyncio
import json
from typing import List, Dict, Any

# -----------------------------------------------
#  PATH SETUP
# -----------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# -----------------------------------------------
#  CONFIGURATION
# -----------------------------------------------

# Load .env manually to avoid extra dependencies
def load_env(path: str):
    if not os.path.exists(path):
        return
    with open(path, 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")

load_env(os.path.join(PROJECT_ROOT, '.env'))

# -----------------------------------------------
#  IMPORTS
# -----------------------------------------------
from infrastructure.outbound.llm.config import VercelAIConfig
from infrastructure.outbound.llm.vercel import VercelAIAdapter
from domain.entities.llm_request.payload import Payload
from domain.value_objects.llm_request.message import Message, Role, create_message
from domain.value_objects.llm_request.model import SelectedModel, GithubModels, get_selected_model
from domain.value_objects.llm_request.tool import ToolDefinition
from domain.value_objects.llm_response.intent.intent import create_intent
from domain.value_objects.llm_request.temperature import create_temperature
from domain.value_objects.llm_request.max_tokens import create_max_tokens

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from infrastructure.outbound.mcp.client_manager import MCPClientManager
from infrastructure.outbound.mcp.tool_executor import MCPToolExecutor
import httpx

# -----------------------------------------------
#  HELPERS
# -----------------------------------------------

# -----------------------------------------------
#  HELPERS
# -----------------------------------------------

async def fetch_mcp_tools(url: str) -> List[ToolDefinition]:
    """Connects to an SSE MCP server and fetches tool definitions."""
    print(f"Connecting to MCP server at {url}...")
    try:
        async with sse_client(url) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                
                tool_definitions = []
                for tool in tools_response.tools:
                    tool_definitions.append(ToolDefinition(
                        name=tool.name,
                        description=tool.description or "",
                        parameters=tool.inputSchema
                    ))
                print(f"Fetched {len(tool_definitions)} tools.")
                return tool_definitions
    except Exception as e:
        print(f"Error fetching tools from {url}: {e}")
        return []

# -----------------------------------------------
#  MAIN TEST
# -----------------------------------------------

def main():
    # 1. Configuration
    # Map GITHUB_PAT to GITHUB_API_KEY as expected by VercelAIConfig
    github_key = os.environ.get("GITHUB_PAT") or os.environ.get("GITHUB_API_KEY", "")
    
    # 2. Setup MCP Infrastructure
    mcp_config = [
        {
            "name": "aws-microservice",
            "type": "sse",
            "config": {"url": "http://localhost:8080/mcp/sse"}
        }
    ]
    client_manager = MCPClientManager(mcp_config)
    tool_executor = MCPToolExecutor(client_manager)

    llm_config = VercelAIConfig(
        github_api_key=github_key,
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        google_api_key=os.environ.get("GOOGLE_API_KEY", ""),
        tool_executor=tool_executor
    )

    # 2. Initialize Adapter
    adapter = VercelAIAdapter(Config=llm_config)

    # 3. Load MCP Tools (Example: AWS Microservice)
    mcp_url = "http://localhost:8080/mcp/sse"
    # Run the async fetch in a dedicated loop
    import anyio
    tools = anyio.run(fetch_mcp_tools, mcp_url)

    if not tools:
        print("Warning: No tools found. Using mock tools for demonstration.")
        # ...
        return

    # 4. Prepare Payload
    intent = create_intent(primary="information_request", secondary=[], confidence=1.0)
    
    # Try to use Groq model for fast and stable verification
    from domain.value_objects.llm_request.model import GroqModels
    model = get_selected_model(GroqModels.LLAMA3_3_70B)
    print(f"Using Groq model: {model.id}")

    # Simple query that should use a tool
    user_query = "Extract the secrets from id Shopify-Test"
    print(f"\nUser Query: {user_query}")
    
    message = create_message(Role.USER, user_query)
    
    system_prompt_str = "You are a helpful assistant with access to various MCP tools. All secrets are stored on AWS."
    system_prompt = create_message(Role.SYSTEM, system_prompt_str)
    
    payload = Payload(
        intent=intent,
        model=model,
        system_prompt=system_prompt,
        message=message,
        tools=tools,
        temperature=create_temperature(0), # Low temperature for tool selection
        max_tokens=create_max_tokens(1000)
    )

    # 5. Ask LLM
    print("Calling LLM...")
    try:
        response = adapter.ask(payload)
        
        print("\n--- LLM Response ---")
        print(f"Text Output: {response.text}")
        
    except Exception as e:
        print(f"Error calling LLM: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pass  # the adapter has nothing to stop

if __name__ == "__main__":
    main()
