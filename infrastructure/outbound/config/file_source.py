import json
import os

from application.dtos.outbound.config import ConfigError, Loaded
from application.ports.outbound.config_ports import ConfigSourcePort


class FileConfigSource(ConfigSourcePort):
    """
    Reads the configuration from the folders of the project: profiles/, flows/, step_defs/, model_sets/ (one JSON file each)
    and the prompt files. A folder or a file whose name starts with `_` is not loaded (`profiles/_unverified/`).
    A file that cannot be read is reported by name in `Loaded.errors`; the others are still loaded.
    """

    def __init__(self, root: str) -> None:
        self.root = os.path.abspath(root)

    def load_profiles(self) -> Loaded:
        return self._load("profiles")

    def load_flows(self) -> Loaded:
        return self._load("flows")

    def load_step_defs(self) -> Loaded:
        return self._load("step_defs")

    def load_model_sets(self) -> Loaded:
        return self._load("model_sets")

    def load_state_fields(self) -> Loaded:
        loaded = Loaded()
        path = os.path.join(self.root, "config", "state_fields.json")
        if not os.path.isfile(path):
            return loaded
        try:
            data = self._read(path, "state_fields")
            fields = data.get("fields")
            if not isinstance(fields, dict):
                raise ConfigError("config/state_fields.json must hold an object `fields`")
            loaded.items.update(fields)
        except ConfigError as error:
            loaded.errors["state_fields"] = str(error)
        return loaded

    def load_prompt(self, name: str) -> str:
        path = self._inside_root(name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError as error:
            raise ConfigError(f"{name}: the prompt cannot be read ({error.strerror or type(error).__name__})")

    # -----------------------------------------------

    def _inside_root(self, name: str) -> str:
        """A name comes from a configuration file: it must stay inside the project."""
        path = os.path.abspath(os.path.join(self.root, name))
        if os.path.isabs(name) or os.path.commonpath([self.root, path]) != self.root:
            raise ConfigError(f"{name}: a prompt must be a path inside the project")
        return path

    def _load(self, folder: str) -> Loaded:
        loaded = Loaded()
        base = os.path.join(self.root, folder)
        if not os.path.isdir(base):
            return loaded

        for file_name in sorted(os.listdir(base)):
            path = os.path.join(base, file_name)
            if not file_name.endswith(".json") or file_name.startswith("_") or not os.path.isfile(path):
                continue
            name = file_name[:-len(".json")]
            try:
                loaded.items[name] = self._read(path, name)
            except ConfigError as error:
                loaded.errors[name] = str(error)
        return loaded

    @staticmethod
    def _read(path: str, name: str) -> dict:
        label = os.path.join(os.path.basename(os.path.dirname(path)), os.path.basename(path))
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as error:
            raise ConfigError(f"{label} is not valid JSON: line {error.lineno}, column {error.colno}: {error.msg}")
        except OSError as error:
            raise ConfigError(f"{label} cannot be read ({error.strerror or type(error).__name__})")

        if not isinstance(data, dict):
            raise ConfigError(f"{label} must hold a JSON object")
        if "name" in data and data["name"] != name:
            raise ConfigError(f"{label}: its name is {data['name']!r}, the name of the file is {name!r}")
        return data
