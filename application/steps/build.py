# ===============================================
#  BUILD A STEP
#  The function a flow runs for a step, made from the step's registry entry (steps/registry.py). A step file that needs
#  more than its constants offers `build_step(runner, mcp_list, mcp_tools)`; an LLM step with one PhaseSpec is run by the
#  runner; a code step is its `run(state)`. The runner is the engine's PhaseRunner (not imported here: a step never imports the engine).
# ===============================================

from typing import Callable, Optional

from application.engine.state.flow_state import FlowState
from application.steps.phase import PhaseSpec
from application.steps.registry import CODE, step as registered_step


def build_step_function(name: str, runner, mcp_list: list, mcp_tools: Optional[object] = None) -> Callable[[FlowState], None]:
    entry = registered_step(name)
    module = entry.module
    if hasattr(module, "build_step"):
        return module.build_step(runner, mcp_list, mcp_tools)
    if entry.kind == CODE:
        return module.run
    specs = [value for value in vars(module).values() if isinstance(value, PhaseSpec)]
    if len(specs) != 1:
        raise ValueError(f"step {name!r}: {module.__name__} must hold one PhaseSpec or a build_step(), it holds {len(specs)}")
    spec = specs[0]
    return lambda state: spec.apply(state, runner.run_phase(spec, state))
