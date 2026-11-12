import json
import os
from typing import Any, List, Optional

from application.ports.outbound.environment_ports import ResourcePort, SettingsPort

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


class FileResources(ResourcePort):
    """The files of the project folder."""

    def __init__(self, root: str = PROJECT_ROOT) -> None:
        self.root = root

    def _path(self, relative_path: str) -> str:
        return os.path.join(self.root, *relative_path.split("/"))

    def read_text(self, relative_path: str) -> str:
        with open(self._path(relative_path), "r", encoding="utf-8") as f:
            return f.read()

    def read_json(self, relative_path: str) -> Any:
        with open(self._path(relative_path), "r", encoding="utf-8") as f:
            return json.load(f)

    def list_files(self, relative_dir: str) -> List[str]:
        folder = self._path(relative_dir)
        if not os.path.isdir(folder):
            return []
        return sorted(name for name in os.listdir(folder) if os.path.isfile(os.path.join(folder, name)))


class EnvironmentSettings(SettingsPort):
    """The environment variables of the process, read each time."""

    def get(self, name: str) -> Optional[str]:
        return os.environ.get(name)
