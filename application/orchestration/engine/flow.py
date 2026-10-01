# ===============================================
#  FLOW
#  An agent is a flow: its name, the steps it runs in order, and the two things that
#  are its own (where to jump after a step, how its result is built). The Pipeline runs
#  any flow. A new agent = a file in flows/ with its steps, built from the files in phases/.
# ===============================================

from dataclasses import dataclass
from typing import Callable, List, Optional

from application.orchestration.state.flow_state import FlowState
from application.orchestration.state.paused_run import FlowResult
from application.orchestration.phases.phase import Step
from application.orchestration.engine.phase_runner import PhaseRunner
from application.outbound.ports.mcp_ports import McpToolsPort
from domain.value_objects.message import Message


@dataclass(frozen=True)
class FlowContext:
    """What the steps of a flow are built with."""
    runner: PhaseRunner
    mcp_list: list
    mcp_tools: Optional[McpToolsPort] = None


@dataclass(frozen=True)
class Flow:
    name: str                                                          # public name: "conversation-flow"
    build_steps: Callable[[FlowContext], List[Step]]
    # Runs after every step: the name of the step to jump to next, or None to go on with the following one.
    jump_after: Optional[Callable[[Step, FlowState], Optional[str]]] = None
    build_result: Callable[[FlowState], FlowResult] = lambda state: FlowResult(reply=state.final_text())
    # The state a new message starts with: the user message and the earlier turns. A flow that keeps more
    # than the shared FlowState holds gives its own (a subclass).
    new_state: Callable[[str, List[Message]], FlowState] = lambda message, history: FlowState(message=message, history=history)
