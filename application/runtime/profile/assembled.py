# ===============================================
#  THE ASSEMBLED AGENT
#  What assemble.py builds and the runtime reads: the profiles that are fine, the flows built from their files, the step
#  declarations and the problems of what is not. Plain data: the runtime never imports assemble.py, only this file.
# ===============================================

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from domain.errors.config_error import ConfigError
from application.runtime.flow.flow import Flow
from application.runtime.step.model_selection import ModelResolver
from application.support.llm.prompt_overrides import PromptOverride

DEFAULT_PROFILE = "default"                       # the profile of a request with no profile: it needs no token


@dataclass
class AssembledProfile:
    name: str
    definition: dict
    flow_name: Optional[str]                 # None when the profile lists its own steps
    steps: List[str]                         # in order; empty when the flow is a Python flow (until T-05.12)
    resolver: ModelResolver
    default_return: str
    requires: List[str] = field(default_factory=list)       # inputs the request must carry
    accepts: List[str] = field(default_factory=list)
    prompts: Dict[str, PromptOverride] = field(default_factory=dict)     # step -> what the profile does to its prompt (T-05.14)
    profile_hash: str = ""                    # SHA-256 (hex) of what the profile is made of, without its token hash (T-05.15)
    flow: Optional[Flow] = None               # the Flow of a profile that lists its own `steps` (named like the profile, T-08.10); None for a flow file


@dataclass
class Agent:
    profiles: Dict[str, AssembledProfile]
    problems: Dict[str, List[str]]           # "<kind>/<name>" -> every problem of that file
    flows: Dict[str, Flow] = field(default_factory=dict)     # the flow files that are fine, built
    step_defs: Dict[str, dict] = field(default_factory=dict)  # the step declarations that are fine
    step_prompts: Dict[str, str] = field(default_factory=dict)  # step -> its prompt, read through the configuration source

    def profile(self, name: str) -> AssembledProfile:
        if name not in self.profiles:
            raise KeyError(name)
        return self.profiles[name]

    def disabled(self) -> Dict[str, str]:
        """Profile name -> why it cannot be used (a profile whose file could not even be read is here too)."""
        return {key[len("profiles/"):]: "; ".join(messages) for key, messages in self.problems.items() if key.startswith("profiles/")}

    def all_problems(self) -> List[str]:
        return [message for messages in self.problems.values() for message in messages]

    def raise_on_errors(self) -> None:
        """Strict mode (tests, check_agent.py): the first problem stops everything."""
        if self.problems:
            raise ConfigError(self.all_problems()[0])
