# ===============================================
#  ENVIRONMENT
#  How the application reaches the files that ship with the project and the settings of a run, without opening a file or reading
#  the environment itself: the composition root (or a script, or the tests) installs the two ports once, before anything else is
#  imported that reads a file (the step catalog does, at import). Clean architecture: the application asks, infrastructure does.
# ===============================================

from typing import Any, List, Optional

from application.ports.outbound.environment_ports import ResourcePort, SettingsPort

_resources: Optional[ResourcePort] = None
_settings: Optional[SettingsPort] = None


def install(resources: ResourcePort, settings: SettingsPort) -> None:
    global _resources, _settings
    _resources = resources
    _settings = settings


def _resource_port() -> ResourcePort:
    if _resources is None:
        raise RuntimeError("the environment is not installed: call composition_root.environment.install_environment() "
                           "before the first import of the application")
    return _resources


def read_text(relative_path: str) -> str:
    return _resource_port().read_text(relative_path)


def read_json(relative_path: str) -> Any:
    return _resource_port().read_json(relative_path)


def list_files(relative_dir: str) -> List[str]:
    return _resource_port().list_files(relative_dir)


def setting(name: str, default: Optional[str] = None) -> Optional[str]:
    """The value of a setting, or `default` when it is not set."""
    if _settings is None:
        raise RuntimeError("the environment is not installed: call composition_root.environment.install_environment() "
                           "before the first import of the application")
    value = _settings.get(name)
    return default if value is None else value
