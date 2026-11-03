# ===============================================
#  BUILD A STEP
#  The function a flow runs for a step. An `llm` step is built from its declaration (step_defs/<name>.json, steps/declared.py); a
#  `code` step is the function of its Python file (steps/registry.py): its `run(state)`, or `build_step(...)` when it needs more
#  than the state (the action executor). The runner is the engine's PhaseRunner (not imported here: a step never imports the engine).
# ===============================================

from typing import Callable, Dict, Optional

from application.engine.state.flow_state import FlowState
from application.steps.declared import repository_declarations, step_function
from application.steps.registry import LLM, step as registered_step


def build_step_function(name: str, runner, mcp_list: list, mcp_tools: Optional[object] = None,
                        declarations: Optional[Dict[str, dict]] = None) -> Callable[[FlowState], None]:
    """`declarations`: the step declarations of the agent (those of the repository when none are given)."""
    declared = declarations if declarations is not None else repository_declarations()
    declaration = declared.get(name)
    if declaration is not None and declaration.get("kind") == LLM:
        return step_function(declaration, runner, mcp_list, mcp_tools)
    if declaration is not None and declaration.get("kind") != "code":
        raise ValueError(f"step {name!r} is run once per action by the action executor: a flow cannot list it")

    module = registered_step(name).module                   # a code step: its Python file
    if hasattr(module, "build_step"):
        return module.build_step(runner, mcp_list, mcp_tools, declared)
    return module.run
