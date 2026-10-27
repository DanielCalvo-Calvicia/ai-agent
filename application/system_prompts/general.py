import os
from typing import Callable, Optional

from application.orchestration.support.clock import now_text
from application.orchestration.phases.catalog import PHASES
from domain.value_objects.llm_request.message import Message, Role, create_message

# Resolved from this file, so it does not depend on the current working directory.
PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')

# Phase 0 is not a phase: it holds the rules that apply to every phase.
GENERIC_PROMPT_FILE = "prompts/0_generic_prompt.txt"
CAPABILITIES_FILE = "prompts/capabilities.txt"


def _read(relative_path: str) -> str:
    with open(os.path.join(PROJECT_ROOT, relative_path), 'r', encoding='utf-8') as f:
        return f.read()


def prompt_file_of(phase: int) -> Optional[str]:
    """The prompt file of a phase (0 = the rules of every phase), or None for an unknown phase or one without a file."""
    if phase == 0:
        return GENERIC_PROMPT_FILE

    info = PHASES.get(phase)
    return info.prompt_file if info else None


def LoadSystemPrompt(phase: int) -> Optional[str]:
    """The text of the prompt file of a phase, or None for an unknown phase."""
    filename = prompt_file_of(phase)
    if filename is None:
        return None

    return _read(filename)


def LoadCapabilities() -> str:
    """What the robot can and cannot do (prompts/capabilities.txt)."""
    return _read(CAPABILITIES_FILE)


def build_system_prompt_from_file(prompt_file: Optional[str], clock: Optional[Callable[[], str]] = None) -> Message:
    """
    The SYSTEM message of a phase: the generic invariants (phase 0), then what the robot can do
    and the current date and time, then the prompt file of the phase.
    """
    parts = [
        _read(GENERIC_PROMPT_FILE),
        LoadCapabilities(),
        f"CURRENT DATE AND TIME: {(clock or now_text)()}",
        _read(prompt_file) if prompt_file else None,
    ]

    return create_message(Role.SYSTEM, "\n\n".join(part for part in parts if part))


def build_system_prompt(phase: int, clock: Optional[Callable[[], str]] = None) -> Message:
    """The SYSTEM message of a phase number (see build_system_prompt_from_file)."""
    return build_system_prompt_from_file(prompt_file_of(phase), clock)
