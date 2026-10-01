# Phase 5 - MCP Operator
# Runs one MCP tool call action with the tools of the MCP servers. One LLM call per action (phase 6 cleans the result).

from typing import Dict, Optional

from domain.value_objects.model import GithubModels

from application.orchestration.support.action_tree import with_outputs
from application.orchestration.state.flow_state import FlowState
from application.orchestration.support.mcp_servers import describe_servers
from application.orchestration.phases.phase import ActionPhaseSpec
from application.orchestration.support.schemas import ACTIONS_SCHEMA_FILE
from application.outbound.ports.mcp_ports import McpToolsPort

# --- What this phase uses ---------------------------------------------------
PHASE_ID = 5
STEP_NAME = "mcp_operator"
MODEL_ENV_VAR = "AI_AGENT_MODEL_PHASE_5"
DEFAULT_MODEL = GithubModels.GPT_4_1
PROMPT_FILE = "prompts/5_mcp_operator.txt"
FORMAT_NAME = "phase5_single_action_response_format"
INTENT = ("decision_support", (), 0.9)
ACTIONS_SCHEMA = ACTIONS_SCHEMA_FILE
# -----------------------------------------------------------------------------

MCP_OPERATOR = ActionPhaseSpec(
    id=PHASE_ID,
    step_name=STEP_NAME,
    prompt_file=PROMPT_FILE,
    model=DEFAULT_MODEL,
    intent=INTENT,
    format_name=FORMAT_NAME,
    schema_file=ACTIONS_SCHEMA,
)


def build_extra(
    state: FlowState,
    mcp_list: list,
    mcp_tools: Optional[McpToolsPort],
    dependency_outputs: Dict[str, str],
    subaction_outputs: Dict[str, str],
) -> dict:
    """What the operator is told besides the action: the MCP servers, the safety verdict and earlier results."""
    return with_outputs(
        {
            "available_mcp_servers": describe_servers(mcp_list, mcp_tools),
            "safety_and_validation": state.safety_and_validation,
        },
        dependency_outputs,
        subaction_outputs,
    )
