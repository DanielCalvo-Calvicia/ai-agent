from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class RequestRecord:
    """Immutable snapshot of a single LLM call."""
    request_id: str
    phase_id: int
    phase_name: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    action_id: Optional[str] = None
    profile: str = ""
    flow: str = ""
    client: str = ""
    profile_hash: str = ""            # SHA-256 (hex) of the assembled profile, without its token hash
    cost_usd: Optional[float] = None  # None: the model has no price in config/
    duration_ms: Optional[int] = None  # the wall time of the call of the step (T-08.2); None when nobody measured it

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id":       self.request_id,
            "phase_id":         self.phase_id,
            "phase_name":       self.phase_name,
            "model":            self.model,
            "prompt_tokens":    self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens":     self.total_tokens,
            "action_id":        self.action_id,
            "profile":          self.profile,
            "flow":             self.flow,
            "step":             self.phase_name,
            "client":           self.client,
            "profile_hash":     self.profile_hash,
            "cost_usd":         self.cost_usd,
        }                                  # no duration_ms here: the summary is in the golden file and a time is never the same twice
