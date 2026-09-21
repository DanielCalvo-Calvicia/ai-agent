import os
from typing import Callable, Optional

from application.orchestration.clock import now_text
from domain.value_objects.message import Message, Role, create_message

# Resolved from this file, so it does not depend on the current working directory.
PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
PATH_SYSTEM_PROMPT = os.path.join(PROJECT_ROOT, 'prompts', 'advanced')
CAPABILITIES_FILE = os.path.join(PROJECT_ROOT, 'prompts', 'capabilities.txt')

# phase -> prompt file. Phase 0 holds the rules that apply to every phase.
_PROMPT_FILES = {
    0: '0_generic_prompt.txt',
    1: '1_triage_specialist.txt',
    2: '2_project_manager.txt',
    3: '3_safety_quality_gatekeeper.txt',
    4: '4_cognitive_worker.txt',
    5: '5_mcp_operator.txt',
    6: '6_data_engineer.txt',
    7: '7_drawf_writter.txt',
    8: '8_editor_in_chief.txt',
    9: '9_answer_checker.txt',
}


def _read(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def LoadSystemPrompt(phase: int) -> Optional[str]:
    """The text of the prompt file of a phase, or None for an unknown phase."""
    filename = _PROMPT_FILES.get(phase)
    if filename is None:
        return None

    return _read(os.path.join(PATH_SYSTEM_PROMPT, filename))


def LoadCapabilities() -> str:
    """What the robot can and cannot do (prompts/capabilities.txt)."""
    return _read(CAPABILITIES_FILE)


def build_system_prompt(phase: int, clock: Optional[Callable[[], str]] = None) -> Message:
    """
    The SYSTEM message of a phase: the generic invariants (phase 0), then what the robot can do
    and the current date and time, then the prompt of the phase.
    """
    parts = [
        LoadSystemPrompt(phase=0),
        LoadCapabilities(),
        f"CURRENT DATE AND TIME: {(clock or now_text)()}",
        LoadSystemPrompt(phase=phase),
    ]

    return create_message(Role.SYSTEM, "\n\n".join(part for part in parts if part))
