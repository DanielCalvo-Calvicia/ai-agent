"""What the Dynamics protocols share: how an answer is read. Pure functions on text (T-07.5, T-07.2 contract of 2026-11-11)."""

import re
from typing import Dict, List, Optional, Tuple

from infrastructure.outbound.mcp.job_protocol import DONE, RUNNING, UNKNOWN

_JOB_STILL_WORKING = re.compile(r"\b(queued|running|pending)\b", re.IGNORECASE)
_SECTION_START = re.compile(r"(?m)^(?=## )")


def head_lines(answer: str) -> Dict[str, str]:
    """The `key: value` lines at the top of an answer or of a `## title` section, up to the first blank line; later lines
    (tables, notes) are not read, so a customer called "Running Ltd" cannot make a finished result look like a job that still runs."""
    head: Dict[str, str] = {}
    for line in answer.replace("\r\n", "\n").split("\n"):
        if not line.strip():
            break
        key, separator, value = line.partition(":")
        if separator and key.strip() and " " not in key.strip():
            head[key.strip().lower()] = value.strip()
    return head


def split_sections(answer: str) -> Tuple[str, List[str]]:
    """The text before the first `## title` line and each section (its title line included); joined again they are the answer."""
    parts = _SECTION_START.split(answer.replace("\r\n", "\n"))
    return parts[0], parts[1:]


def optional_int(value: Optional[str]) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def read_state(answer: str) -> str:
    """What an answer of the read tool says: a result (it has `returned`), a job that still works, or something else."""
    head = head_lines(answer)
    if head.get("status", "").lower() == "running":
        return RUNNING
    if "returned" in head:
        return DONE
    if _JOB_STILL_WORKING.search(answer.replace("\r\n", "\n").split("\n\n", 1)[0]):     # the text above the first blank line, in any wording
        return RUNNING
    return UNKNOWN
