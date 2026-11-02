from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict


class ConfigError(ValueError):
    """A file of the configuration cannot be used. The message names the file."""


@dataclass
class Loaded:
    """What one source gave for one kind of file: the files that could be read, and why the others could not."""
    items: Dict[str, dict] = field(default_factory=dict)      # name (the file name without .json) -> the parsed object
    errors: Dict[str, str] = field(default_factory=dict)      # name -> what is wrong with that file


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
    def load_prompt(self, name: str) -> str:
        """The text of a prompt, by the name a step or a profile gives it (for example `prompts/7_drawf_writter.txt`)."""
        raise NotImplementedError
