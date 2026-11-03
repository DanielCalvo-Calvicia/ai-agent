# ===============================================
#  FLOW
#  A flow is its name, the steps it runs in order, and what is its own: how its result is built and what happens when a
#  step asks the user. The Pipeline runs any flow. A flow is a file in flows/ (engine/flow_file.py builds this object
#  from it); the tests may also make one by hand.
# ===============================================

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from application.engine.state.flow_state import FlowState
from application.engine.state.paused_run import FlowResult
from application.steps.hooks import ANSWER_CHECKER, USER_CLARIFICATION
from application.steps.phase import Step
from application.engine.phase_runner import PhaseRunner
from application.outbound.ports.mcp_ports import McpToolsPort, ToolScope
from domain.value_objects.llm_request.message import Message


@dataclass(frozen=True)
class FlowContext:
    """What the steps of a flow are built with."""
    runner: PhaseRunner
    mcp_list: list
    mcp_tools: Optional[McpToolsPort] = None
    scope_of: Optional[Callable[[str], ToolScope]] = None     # the tools a step may use (profile, flow and step limits)
    step_defs: Optional[Dict[str, dict]] = None                # the step declarations of the agent (None: those of the repository)


@dataclass(frozen=True)
class Flow:
    name: str                                                          # public name: "conversation"
    build_steps: Callable[[FlowContext], List[Step]]
    # Runs after every step: the name of the step to jump to next, or None to go on with the following one.
    jump_after: Optional[Callable[[Step, FlowState], Optional[str]]] = None
    build_result: Callable[[FlowState], FlowResult] = lambda state: FlowResult(reply=state.final_text())
    # The state a new message starts with: the user message and the earlier turns. A flow that keeps more
    # than the shared FlowState holds gives its own (a subclass).
    new_state: Callable[[str, List[Message]], FlowState] = lambda message, history: FlowState(message=message, history=history)
    # The hooks that run when a step asks the user and when the user answers (steps/hooks.py). None: the flow cannot ask.
    on_pause: Optional[str] = USER_CLARIFICATION
    on_resume: Optional[str] = ANSWER_CHECKER
    # The tool limits of the flow file: for the whole flow and for single steps (a `tools` object each; None sets no limit).
    tools: Optional[dict] = None
    step_tools: Dict[str, dict] = field(default_factory=dict)
