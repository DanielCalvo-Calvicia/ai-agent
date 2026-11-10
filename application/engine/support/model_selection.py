# ===============================================
#  MODEL SELECTION
#  Which LLMs answer a step, as an ordered list: the first one answers, the next ones are tried when it is out of
#  capacity (ADR-014). The most specific value wins and the whole list is replaced (PR-005 section 5). From most to
#  least specific, in the profile that is asked:
#    1. flows.<flow>.steps.<step>.models      that step, in that flow
#    2. overrides.<step>.models               that step, in every flow
#    3. flows.<flow>.models                   every step of that flow
#    4. models                                every step
#    5. the default model of the step         (its DEFAULT_MODEL), when no level says anything
#  A level is an ordered list of model ids, or the name of a model set (model_sets/<name>.json: a table with `default`
#  and one entry per step, each an ordered list). An unknown step, model set or model fails loudly, and says where.
#  No environment variable chooses a model any more (T-05.5).
# ===============================================

from typing import Any, Dict, List, Optional, Tuple

from application.engine.support.metrics import ALL_PHASE_NAMES, PHASE_NAMES
from domain.value_objects.llm_request.model import GoogleModels, SelectedModel, get_selected_model

# The steps of the text flows (identification, conversation, special): what the cost, budget and ratings tables cover. A step of the movement
# or the expression flow (motion_planner, emotion_reader) can be set in a model set or a profile too; it is only left out of those tables.
STEP_NAMES = list(PHASE_NAMES.values())
ALL_STEP_NAMES = list(ALL_PHASE_NAMES.values())

DEFAULT_KEY = "default"
# The model set the service runs on until profiles choose theirs (T-05.7): the profile that was active in config/step_models.json.
DEFAULT_MODEL_SET = "proven"
_NOT_AN_ENTRY = ("schema_version", "name")             # keys of a model set that are not a step; so are the ones that start with `_`


def _as_selected(model_id: str, where: str) -> SelectedModel:
    try:
        return get_selected_model(model_id)
    except (ValueError, TypeError):
        raise ValueError(f"{where}: {model_id!r} is not a model of the catalog (domain/value_objects/llm_request/model_catalog.py)")


def _check_list(value: Any, where: str) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{where}: must be a list of model ids, the first one answers and the next ones are the fallback")
    for model_id in value:
        _as_selected(str(model_id), where)


def check_model_set(name: str, data: dict) -> None:
    """Fails with a clear message on an unknown step or model, so a typo is not silently ignored."""
    where = f"model_sets/{name}.json"
    entries = 0
    for key, value in data.items():
        if key.startswith("_") or key in _NOT_AN_ENTRY:
            continue
        if key != DEFAULT_KEY and key not in ALL_STEP_NAMES:
            raise ValueError(f"{where}: unknown step {key!r}. Steps: {', '.join(ALL_STEP_NAMES)}")
        _check_list(value, f"{where}: {key}")
        entries += 1
    if not entries:
        raise ValueError(f"{where}: a model set needs `{DEFAULT_KEY}` or at least one step")


class ModelResolver:
    """The models of every step of one profile (a dict as profiles/<name>.json has it), by flow and step."""

    def __init__(self, profile: Optional[dict] = None, model_sets: Optional[Dict[str, dict]] = None) -> None:
        self.profile = profile or {}
        self.model_sets = model_sets or {}
        self._check()

    # -----------------------------------------------

    def models_for(self, flow: str, step: str, default: GoogleModels) -> List[SelectedModel]:
        """The ordered list for a step of a flow: the first answers, the rest is the fallback. The step's default when the profile says nothing."""
        ids, _ = self._choose(flow, step)
        if ids is None:
            return [get_selected_model(default)]
        return [get_selected_model(model_id) for model_id in ids]

    def source_for(self, flow: str, step: str) -> str:
        """Where the choice for a step comes from (`overrides.project_manager`, `models (set claude_mixed)`, `step default`)."""
        return self._choose(flow, step)[1]

    # -----------------------------------------------

    def _levels(self, flow: str, step: str) -> List[Tuple[str, Any]]:
        flows = self.profile.get("flows") or {}
        flow_entry = flows.get(flow) or {}
        return [
            (f"flows.{flow}.steps.{step}", ((flow_entry.get("steps") or {}).get(step) or {}).get("models")),
            (f"overrides.{step}", ((self.profile.get("overrides") or {}).get(step) or {}).get("models")),
            (f"flows.{flow}", flow_entry.get("models")),
            ("models", self.profile.get("models")),
        ]

    def _choose(self, flow: str, step: str) -> Tuple[Optional[List[str]], str]:
        for source, value in self._levels(flow, step):
            ids = self._ids(value, step)
            if ids:
                return ids, f"{source} (set {value})" if isinstance(value, str) else source
        return None, "step default"

    def _ids(self, value: Any, step: str) -> Optional[List[str]]:
        if value is None:
            return None
        if isinstance(value, str):
            model_set = self.model_sets[value]
            return model_set.get(step) or model_set.get(DEFAULT_KEY)
        return list(value)

    def _check(self) -> None:
        """Every level the profile writes: a list of known models, or the name of a model set that exists and is right."""
        checked = set()

        def check(value: Any, where: str) -> None:
            if value is None:
                return
            if isinstance(value, str):
                if value not in self.model_sets:
                    raise ValueError(f"{where}: unknown model set {value!r}. Model sets: {', '.join(self.model_sets) or 'none'}")
                if value not in checked:
                    check_model_set(value, self.model_sets[value])
                    checked.add(value)
                return
            _check_list(value, where)

        check(self.profile.get("models"), "profile models")
        for flow, entry in (self.profile.get("flows") or {}).items():
            check((entry or {}).get("models"), f"profile flows.{flow}.models")
            for step, step_entry in ((entry or {}).get("steps") or {}).items():
                self._known_step(step, f"profile flows.{flow}.steps")
                check((step_entry or {}).get("models"), f"profile flows.{flow}.steps.{step}.models")
        for step, step_entry in (self.profile.get("overrides") or {}).items():
            self._known_step(step, "profile overrides")
            check((step_entry or {}).get("models"), f"profile overrides.{step}.models")

    @staticmethod
    def _known_step(step: str, where: str) -> None:
        if step not in ALL_STEP_NAMES:
            raise ValueError(f"{where}: unknown step {step!r}. Steps: {', '.join(ALL_STEP_NAMES)}")


def effective_models(resolver: ModelResolver, flow: str = "") -> Dict[str, Tuple[str, str]]:
    """step name -> (the model that answers it, where the choice comes from), for the steps of the text flows. Without touching the network."""
    from application.steps.catalog import PHASES

    result = {}
    for phase_id, name in PHASE_NAMES.items():
        models = resolver.models_for(flow, name, PHASES[phase_id].default_model)
        result[name] = (models[0].id, resolver.source_for(flow, name))
    return result
