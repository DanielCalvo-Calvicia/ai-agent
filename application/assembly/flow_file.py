# ===============================================
#  FLOW FILE
#  Builds the Flow object the Pipeline runs from the JSON of a flow file (flows/<name>.json, PR-005 section 3.3): an ordered
#  list of steps with named pause and retry rules, `on_pause` and `on_resume` hooks and the step the result comes from. The
#  names of steps, conditions and hooks are checked by assemble() before this runs; here they are looked up.
# ===============================================

from typing import Dict, List, Optional

from application.engine.flow import Flow, FlowContext
from application.steps.build import build_step_function
from application.steps.conditions import CONDITIONS
from application.steps.declared import repository_declarations
from application.steps.hooks import result_builder, state_factory
from application.steps.phase import Step
from application.outbound.ports.mcp_ports import ToolScope, scoped
from application.steps.registry import step as registered_step


def step_entries(data: dict) -> List[dict]:
    """The steps of a flow file as dictionaries: a plain name is a step with no rules."""
    return [entry if isinstance(entry, dict) else {"step": entry} for entry in data["steps"]]


def _legacy_id(name: str, step_defs: Optional[Dict[str, dict]]) -> Optional[int]:
    """The old phase number of a step: a label for failures and metrics."""
    declaration = (step_defs if step_defs is not None else repository_declarations()).get(name)
    return declaration["legacy_id"] if declaration and "legacy_id" in declaration else registered_step(name).legacy_id


def flow_from_file(name: str, data: dict) -> Flow:
    entries = step_entries(data)

    def build_steps(context: FlowContext) -> List[Step]:
        steps = []
        for entry in entries:
            name = entry["step"]
            condition = entry.get("pause_if")
            mcp_list, mcp_tools = scoped(context.mcp_list, context.mcp_tools, context.scope_of(name) if context.scope_of else ToolScope())
            steps.append(Step(
                name,
                build_step_function(name, context.runner, mcp_list, mcp_tools, context.step_defs),
                pause_if=CONDITIONS[condition] if condition else None,
                phase_id=_legacy_id(name, context.step_defs),
                retry_on_status=bool(entry.get("retry_on_status")),
            ))
        return steps

    return Flow(
        name=name,
        build_steps=build_steps,
        build_result=result_builder(data.get("result_from")),
        new_state=state_factory(entry["step"] for entry in entries),
        on_pause=data.get("on_pause"),
        on_resume=data.get("on_resume"),
        tools=data.get("tools"),
        step_tools={entry["step"]: entry["tools"] for entry in entries if isinstance(entry.get("tools"), dict)},
    )
