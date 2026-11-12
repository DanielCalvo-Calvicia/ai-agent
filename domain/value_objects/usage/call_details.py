from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CallDetails:
    """What went in and out of one LLM call, and what the user asked in the message it belongs to."""
    message: str = ""
    input_text: Optional[str] = None
    output_text: Optional[str] = None
    started_ns: Optional[int] = None     # wall clock of the first attempt (time.time_ns)
    ended_ns: Optional[int] = None        # wall clock of the answer that was used
    profile: str = ""                     # what the message runs (T-05.15): shown in the trace, never a token or an input
    flow: str = ""
    client: str = ""
    profile_hash: str = ""
