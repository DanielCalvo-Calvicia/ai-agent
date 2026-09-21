# ===============================================
#  MODEL SELECTION
#  Which LLM answers each step. Order of precedence:
#    1. the variable AI_AGENT_MODEL_PHASE_<n>   (n = the phase number: 1..9, 99)
#    2. `steps` of the config file                config/step_models.json
#    3. the active `profile` of that file, for the step
#    4. the `default` of that profile
#    5. the default of the code
#  A value that is null or "" is skipped. An unknown step or model fails loudly.
# ===============================================

import json
import os
from typing import Any, Dict, Optional, Tuple

from application.orchestration.metrics import PHASE_NAMES
from domain.value_objects.model import GithubModels, SelectedModel, get_selected_model

# Model used by the phases that run once per action (4, 5, 6).
ACTION_PHASE_MODEL = GithubModels.GPT_4_1

MODELS_FILE_VARIABLE = "AI_AGENT_MODELS_FILE"
DEFAULT_MODELS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'config', 'step_models.json')

STEP_NAMES = list(PHASE_NAMES.values())
_PHASE_OF = {name: phase for phase, name in PHASE_NAMES.items()}

_cache: Dict[str, Tuple[float, dict]] = {}


def models_file() -> str:
    """The config file: AI_AGENT_MODELS_FILE, or config/step_models.json. It may not exist."""
    return os.path.abspath(os.environ.get(MODELS_FILE_VARIABLE) or DEFAULT_MODELS_FILE)


def _model(value: Any) -> Optional[str]:
    return str(value).strip() if value not in (None, "") else None


def _as_selected(model_id: str, where: str) -> SelectedModel:
    try:
        return get_selected_model(model_id)
    except (ValueError, TypeError):
        raise ValueError(f"{where}: {model_id!r} is not a model of the catalog (domain/value_objects/model_catalog.py)")


def load_config() -> dict:
    """The parsed and checked config file. An empty config when the file does not exist."""
    path = models_file()
    if not os.path.exists(path):
        return {}

    modified = os.path.getmtime(path)
    if path in _cache and _cache[path][0] == modified:
        return _cache[path][1]

    with open(path, "r", encoding="utf-8") as f:
        try:
            config = json.load(f)
        except ValueError as error:
            raise ValueError(f"{path} is not valid JSON: {error}")

    _check(config, path)
    _cache[path] = (modified, config)
    return config


def _check(config: dict, path: str) -> None:
    """Fails with a clear message on an unknown step, profile or model, so a typo is not silently ignored."""
    def check_step_names(names, where):
        for name in names:
            if not name.startswith("_") and name not in STEP_NAMES and name != "default":
                raise ValueError(f"{path}: {where} has an unknown step {name!r}. Steps: {', '.join(STEP_NAMES)}")

    steps = config.get("steps") or {}
    check_step_names(steps, "`steps`")
    for name, model in steps.items():
        if not name.startswith("_") and _model(model):
            _as_selected(_model(model), f"{path}: steps.{name}")

    profiles = config.get("profiles") or {}
    for profile_name, profile in profiles.items():
        check_step_names(profile, f"profile {profile_name!r}")
        for name, model in profile.items():
            if not name.startswith("_") and _model(model):
                _as_selected(_model(model), f"{path}: profiles.{profile_name}.{name}")

    active = _model(config.get("profile"))
    if active and active not in profiles:
        raise ValueError(f"{path}: profile {active!r} is not defined. Profiles: {', '.join(profiles) or 'none'}")


def choose(phase_id: int) -> Tuple[Optional[str], str]:
    """
    The model id chosen for a phase, and where the choice comes from
    (`env`, `steps`, `profile`, `profile default`), or (None, "code default").
    """
    override = os.environ.get(f"AI_AGENT_MODEL_PHASE_{phase_id}", "").strip()
    if override:
        return override, f"env AI_AGENT_MODEL_PHASE_{phase_id}"

    config = load_config()
    name = PHASE_NAMES.get(phase_id)

    chosen = _model((config.get("steps") or {}).get(name))
    if chosen:
        return chosen, "config steps"

    profile = (config.get("profiles") or {}).get(_model(config.get("profile")) or "", {})
    chosen = _model(profile.get(name))
    if chosen:
        return chosen, f"profile {config.get('profile')}"

    chosen = _model(profile.get("default"))
    if chosen:
        return chosen, f"profile {config.get('profile')} default"

    return None, "code default"


def model_for_phase(phase_id: int, default: GithubModels) -> SelectedModel:
    """
    The model of a phase (see the order of precedence at the top of this file).
    The provider is the first one of the catalog that lists the id (OpenAI, Google, Anthropic, Mistral, Cohere,
    Groq, Ollama, then GitHub), and it needs that provider's key and URL.
    """
    chosen, source = choose(phase_id)
    if chosen is None:
        return get_selected_model(default)

    where = source if source.startswith("env") else f"{models_file()} ({source})"
    return _as_selected(chosen, where)


def effective_models() -> Dict[str, Tuple[str, str]]:
    """step name -> (model id in use, where it comes from), for every step. Without touching the network."""
    result = {}
    for phase_id, name in PHASE_NAMES.items():
        model = model_for_phase(phase_id, GithubModels.GPT_4_1 if phase_id != 1 else GithubModels.GPT_4_1_MINI)
        result[name] = (model.id, choose(phase_id)[1])
    return result
