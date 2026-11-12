from abc import ABC, abstractmethod
from typing import Dict

from application.dtos.outbound.config import Loaded


class ConfigSourcePort(ABC):
    """
    Where the agent is made of: its profiles, flows, step declarations, model sets and prompts. They are read once at
    start. The data is plain (no Python inside a file); today they are files, later they may come from another source.
    """

    @abstractmethod
    def load_profiles(self) -> Loaded:
        raise NotImplementedError

    @abstractmethod
    def load_flows(self) -> Loaded:
        raise NotImplementedError

    @abstractmethod
    def load_step_defs(self) -> Loaded:
        raise NotImplementedError

    @abstractmethod
    def load_model_sets(self) -> Loaded:
        raise NotImplementedError

    @abstractmethod
    def load_state_fields(self) -> Loaded:
        """The catalog of the fields a step may read and write: one item per field (config/state_fields.json)."""
        raise NotImplementedError

    @abstractmethod
    def load_prompt(self, name: str) -> str:
        """The text of a prompt, by the name a step or a profile gives it (for example `prompts/7_drawf_writter.txt`)."""
        raise NotImplementedError
