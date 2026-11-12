from abc import ABC, abstractmethod
from typing import Any, List, Optional


class ResourcePort(ABC):
    """The files that ship with the project (prompts, JSON schemas, step declarations), read by a path relative to the project root,
    written with `/`. The application never opens a file itself."""

    @abstractmethod
    def read_text(self, relative_path: str) -> str:
        """The text of a file. Raises OSError when it cannot be read."""
        raise NotImplementedError

    @abstractmethod
    def read_json(self, relative_path: str) -> Any:
        """The parsed JSON of a file. Raises OSError when it cannot be read and ValueError when it is not JSON."""
        raise NotImplementedError

    @abstractmethod
    def list_files(self, relative_dir: str) -> List[str]:
        """The names of the files of a folder, sorted; an empty list when the folder does not exist."""
        raise NotImplementedError


class SettingsPort(ABC):
    """The settings of a run (today environment variables). The application never reads the environment itself."""

    @abstractmethod
    def get(self, name: str) -> Optional[str]:
        """The value of a setting as text, or None when it is not set. Read each time: a setting may change while the service runs (tests)."""
        raise NotImplementedError
