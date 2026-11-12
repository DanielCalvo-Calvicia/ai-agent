# ===============================================
#  CONFIG SNAPSHOT
#  Everything the agent is made of, read once at start from a ConfigSourcePort: plain dictionaries, one per kind of file.
#  The source does not matter here (files today); the checks are the same for any of them. A file that cannot be used
#  is kept in `errors` (by kind and name) instead of stopping the load: assemble() decides what that means, the service
#  disables the profile that needs it, the tests and check_agent.py stop.
# ===============================================

from typing import Dict, Optional

from domain.errors.config_error import ConfigError
from application.ports.outbound.config_ports import ConfigSourcePort
from domain.value_objects.config.loaded import Loaded

SUPPORTED_SCHEMA_VERSIONS = (1,)
KINDS = ("profiles", "flows", "step_defs", "model_sets")


class ConfigSnapshot:
    def __init__(self, source: ConfigSourcePort, profiles: dict, flows: dict, step_defs: dict, model_sets: dict,
                 errors: Dict[str, str], state_fields: Optional[dict] = None) -> None:
        self._source = source
        self._prompts: Dict[str, str] = {}
        self.profiles = profiles
        self.flows = flows
        self.step_defs = step_defs
        self.model_sets = model_sets
        self.state_fields = state_fields or {}      # field name -> its entry of config/state_fields.json
        self.errors = errors                    # "<kind>/<name>" -> what is wrong with that file

    def prompt(self, name: str) -> str:
        """The text of a prompt, read once."""
        if name not in self._prompts:
            self._prompts[name] = self._source.load_prompt(name)
        return self._prompts[name]

    def raise_on_errors(self) -> None:
        """Strict mode (tests, check_agent.py): the first file that cannot be used stops everything."""
        if self.errors:
            raise ConfigError(next(iter(self.errors.values())))


def build_snapshot(source: ConfigSourcePort) -> ConfigSnapshot:
    loaded = {
        "profiles": source.load_profiles(),
        "flows": source.load_flows(),
        "step_defs": source.load_step_defs(),
        "model_sets": source.load_model_sets(),
    }
    errors: Dict[str, str] = {}
    kept: Dict[str, dict] = {}

    for kind in KINDS:
        result: Loaded = loaded[kind]
        kept[kind] = {}
        for name, message in result.errors.items():
            errors[f"{kind}/{name}"] = message
        for name, data in result.items.items():
            problem = _version_problem(kind, name, data)
            if problem:
                errors[f"{kind}/{name}"] = problem
            else:
                kept[kind][name] = data

    fields = source.load_state_fields()
    for name, message in fields.errors.items():
        errors[name] = message

    return ConfigSnapshot(source, kept["profiles"], kept["flows"], kept["step_defs"], kept["model_sets"], errors, fields.items)


def _version_problem(kind: str, name: str, data: dict) -> str:
    version = data.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int):
        return f"{kind}/{name}.json has no integer schema_version"
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        supported = ", ".join(str(v) for v in SUPPORTED_SCHEMA_VERSIONS)
        return f"{kind}/{name}.json: schema_version {version} is not supported (supported: {supported})"
    return ""
