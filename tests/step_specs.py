# The specs of the LLM steps of this repository, built from their declarations (step_defs/*.json). The tests that used the
# Python constants of the step files (before T-05.16) take them from here: the same objects of the same kind.
from application.runtime.step.declared import action_spec, phase_spec, repository_declarations

TRIAGE = phase_spec("triage_specialist")
SAFETY_GATE = phase_spec("safety_quality_gatekeeper")
DRAFT_WRITER = phase_spec("draft_writer")
EDITOR_IN_CHIEF = phase_spec("editor_in_chief")
MOTION_PLANNER = phase_spec("motion_planner")
EMOTION_READER = phase_spec("emotion_reader")
COGNITIVE_WORKER = action_spec("cognitive_worker")
MCP_OPERATOR = action_spec("mcp_operator")
DATA_ENGINEER = action_spec("data_engineer")


def make_project_manager(mcp_list, mcp_tools=None):
    """The planner's spec, with the answer schema that names the MCP servers it may use."""
    return phase_spec("project_manager", mcp_list, mcp_tools)


def prompt_file(step_name):
    return repository_declarations()[step_name]["prompt"]["file"]
