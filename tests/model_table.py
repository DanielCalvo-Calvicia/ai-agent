"""
Builds the tables of Gemini models (docs/models/gemini_models_per_step.md) from config/gemini_models.json, the one
place where prices and ratings are kept, and shows the model sets of model_sets/ next to them.
`python scripts/model_tables.py` shows them and writes the documents.
"""
import json
import os
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MODELS_PATH = os.path.join(PROJECT_ROOT, "config", "gemini_models.json")
MODEL_SETS_DIR = os.path.join(PROJECT_ROOT, "model_sets")
# The order the tables list the sets in (the order of the old step_models.json); a set that is not here goes after them, by name.
SET_ORDER = ("proven", "budget", "balanced", "quality", "budget50", "claude_sonnet", "budget50_groq", "google_free",
             "claude_haiku", "claude_mixed")
DOC_PATH = os.path.join(PROJECT_ROOT, "docs", "models", "gemini_models_per_step.md")

LEVELS = ["best", "good", "ok", "weak", "avoid"]
OK_LEVELS = ("best", "good")


def load_models(path: str = MODELS_PATH) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def blended(model: Dict[str, Any]) -> float:
    """(3 x input + 1 x output) / 4, in USD per 1M tokens."""
    return (3 * model["input"] + model["output"]) / 4


def per_message(model: Dict[str, Any], tokens: int) -> float:
    """What one message costs if every call of it used this model (tokens = the size of a message)."""
    return blended(model) * tokens / 1_000_000


def per_call(model: Dict[str, Any], tokens: int) -> float:
    """What one call of a step costs with this model (tokens = the tokens of that call)."""
    return blended(model) * tokens / 1_000_000


def _money(value: float, decimals: Optional[int] = None) -> str:
    if decimals is not None:
        return f"${value:,.{decimals}f}"
    return f"${value:,.2f}" if value >= 0.1 else f"${value:.4f}" if value < 0.01 else f"${value:.3f}"


def best_options(data: Dict[str, Any], step: str) -> Dict[str, Optional[Dict[str, Any]]]:
    """For a step: the cheapest model rated best, the cheapest rated best or good, and the strongest (last) rated best."""
    models = data["models"]                       # sorted by cost, cheapest first
    best = [m for m in models if m["ratings"][step][0] == "best"]
    good = [m for m in models if m["ratings"][step][0] in OK_LEVELS]
    return {"cheapest_best": best[0] if best else None,
            "cheapest_good": good[0] if good else None,
            "strongest": best[-1] if best else (good[-1] if good else None)}


def markdown(data: Dict[str, Any], config: Dict[str, Any]) -> str:
    steps: Dict[str, str] = data["steps"]
    step_tokens: Dict[str, Dict[str, Any]] = data["step_tokens"]
    models: List[Dict[str, Any]] = data["models"]
    tokens = data["message_tokens"]
    names = list(steps)
    profiles = config.get("profiles", {})
    active = config.get("profile")
    active_profile = profiles.get(active, {})

    def in_use(step: str) -> str:
        return active_profile.get(step) or active_profile.get("default") or "(code default)"

    lines = [
        "# Gemini models for each step",
        "",
        "_Generated from `config/gemini_models.json` by `scripts/model_tables.py --write`. Edit that file, not this one._",
        "",
        f"- {data['_source']}",
        f"- {data['_api_check']}",
        f"- {data['_ratings']}",
        f"- Sorted from the lowest to the highest cost. {data['_blend']}",
        "- Ratings: " + "; ".join(f"**{k}** = {v}" for k, v in data["_levels"].items()) + ".",
        "",
        "## 1. Choose the model of each step (summary)",
        "",
        "For each step: what it uses now, and the options. Costs are per call of that step "
        "(blended price x the tokens of one call, see section 3).",
        "",
        "| Step | Uses now | Tokens per call | Cheapest rated best | Cheapest rated good or best | Strongest |",
        "|---|---|---|---|---|---|",
    ]
    for name in names:
        tok = step_tokens[name]["tokens"]
        opts = best_options(data, name)

        def cell(model):
            return f"`{model['id']}` {_money(per_call(model, tok))}" if model else "none"

        lines.append(f"| {name} | `{in_use(name)}` | {tok:,} | {cell(opts['cheapest_best'])} | "
                     f"{cell(opts['cheapest_good'])} | {cell(opts['strongest'])} |")

    lines += [
        "",
        "To use a model for a step, write it in the model set the profile uses (`model_sets/<name>.json`): an ordered list, "
        "the first model answers and the next ones are tried when it is out of capacity. "
        "The exact line for every model is in the table of its step (section 3).",
        "",
        "## 2. The models and their cost",
        "",
        "| # | Name | Model id | Input $/1M | Output $/1M | Blended $/1M | $ per message | Status | Test call | Thinking |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for number, model in enumerate(models, 1):
        lines.append("| " + " | ".join([
            str(number), model["name"], f"`{model['id']}`", f"{model['input']:.2f}",
            f"{model['output']:.2f}{'*' if model['price_note'] else ''}", _money(blended(model), 2),
            _money(per_message(model, tokens)), model["status"].split(" (")[0].split(",")[0],
            model["api_check"].split(":")[0], model["thinking"]]) + " |")
    lines += ["", *[f"\\* {m['name']}: {m['price_note']}" for m in models if m["price_note"]]]
    lines += ["", "\"$ per message\" is the blended cost of about "
              f"{tokens:,} tokens (one message of this agent: 6 to 7 calls in a row) if all its calls used that model.",
              "", "| Name | Summary |", "|---|---|"]
    lines += [f"| {m['name']} | {m['summary']} |" for m in models]

    lines += [
        "",
        "## 3. One table per step",
        "",
        "Each table lists every model, cheapest first, with its cost for a call of that step and how it should "
        "perform there. `Tokens per call` is what a call of the step used with gemini-2.5-flash in the real runs "
        "(input plus output, thinking included); other models will use somewhat different amounts, and the steps "
        "marked *estimate* were not measured.",
    ]
    for name in names:
        info = step_tokens[name]
        tok = info["tokens"]
        lines += [
            "", f"### {name}", "", steps[name], "",
            f"- Tokens per call: about **{tok:,}** ({info['note']}). Calls per message: {info['calls']}.",
            f"- Uses now: `{in_use(name)}`.", "",
            "| Model | Model id | Input $/1M | Output $/1M | $ per call | $ per 1,000 calls | Rating | Why | Use it |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for model in models:
            level, why = model["ratings"][name]
            lines.append(
                f"| {model['name']} | `{model['id']}` | {model['input']:.2f} | "
                f"{model['output']:.2f}{'*' if model['price_note'] else ''} | {_money(per_call(model, tok))} | "
                f"{_money(per_call(model, tok) * 1000, 2)} | **{level}** | {why} | "
                f"`\"{name}\": [\"{model['id']}\"]` |")

    lines += ["", "## 4. Model sets in `model_sets/`", "",
              f"Set in use: **{active}** (the service runs on it until the profiles choose theirs, T-05.7). "
              "The first model of each entry is shown; the next ones of its list are the fallback.",
              "", "| Step | " + " | ".join(profiles) + " |", "|---|" + "---|" * len(profiles)]
    for name in names:
        cells = [(p.get(name) or p.get("default") or "") for p in profiles.values()]
        lines.append(f"| {name} | " + " | ".join(f"`{c}`" if c else "" for c in cells) + " |")
    lines += [""]
    for profile_name, profile in profiles.items():
        if profile.get("_about"):
            lines.append(f"- **{profile_name}**: {profile['_about']}")

    lines += ["", "## 5. How to choose", "",
              "1. See the options of one step and what it uses now: "
              "`windows\\Scripts\\python.exe scripts\\model_tables.py --step=project_manager`.",
              "2. Choose: write the model in the entry of that step of a model set (`\"project_manager\": [\"gemini-3.8-flash\"]` in "
              "`model_sets/<name>.json`), or in the profile that uses it. To change every step at once: name another model set in the profile "
              "(`budget`, `balanced`, `quality`, `proven`, ...). A change is a file change and a new start: no environment variable chooses a model.",
              "3. A list is an order: the first model answers and the next ones are the fallback when it is out of capacity.",
              "4. Try the model on that step before you trust it: run the flow once with "
              "`tests/manual/debug_flow.py --real`, then repeat the step with `--only=<step> --state=<file> --repeat=5`. "
              "The problems it finds and `compare.md` show if the model is steady.",
              ""]
    return "\n".join(lines)


# ===============================================
#  THE MODEL SETS
# ===============================================

def read_model_sets(path: str = MODEL_SETS_DIR) -> Dict[str, Dict[str, Any]]:
    """The files of model_sets/ by name (a name that starts with `_` is not a set)."""
    names = [n[:-5] for n in os.listdir(path) if n.endswith(".json") and not n.startswith("_")]
    names.sort(key=lambda n: (SET_ORDER.index(n) if n in SET_ORDER else len(SET_ORDER), n))
    sets = {}
    for name in names:
        with open(os.path.join(path, f"{name}.json"), "r", encoding="utf-8") as f:
            sets[name] = json.load(f)
    return sets


def default_resolver():
    """The ModelResolver of the model set the service runs on (what the manual scripts use as the models of the agent)."""
    from application.engine.support.model_selection import DEFAULT_MODEL_SET, ModelResolver

    return ModelResolver({"models": DEFAULT_MODEL_SET}, read_model_sets())


MANUAL_PROFILE = "special"      # the profile the manual scripts run (triage, plan, tools, write, edit); change it here or pass RUN_PROFILE


def manual_service():
    """
    What the manual scripts that call a real model give `SessionService` to run a profile: the real assembled agent and the profile.
    Since T-05.7 a service runs profiles, not a model set; the profile is `RUN_PROFILE` of the environment (default `special`).
    Only the service-level profile is set, so no token is needed.
    """
    from application.engine.assemble import assemble
    from application.engine.config_snapshot import build_snapshot
    from infrastructure.outbound.config.file_source import FileConfigSource

    agent = assemble(build_snapshot(FileConfigSource(PROJECT_ROOT)))
    agent.raise_on_errors()
    return {"agent": agent, "profile": os.environ.get("RUN_PROFILE", MANUAL_PROFILE)}


def manual_resolver():
    """The ModelResolver of the profile the manual scripts run."""
    service = manual_service()
    return service["agent"].profile(service["profile"]).resolver


def read_config(path: str = MODEL_SETS_DIR) -> Dict[str, Any]:
    """
    The model sets in the shape the tables use: `profile` is the set the service runs on and `profiles` has, for each set,
    the first model of every entry (the others of a list are its fallback) and its `_about` text.
    """
    from application.engine.support.model_selection import DEFAULT_MODEL_SET

    profiles: Dict[str, Dict[str, Any]] = {}
    for name, data in read_model_sets(path).items():
        entry: Dict[str, Any] = {}
        if data.get("_about"):
            entry["_about"] = data["_about"]
        for key, ids in data.items():
            if not key.startswith("_") and key not in ("schema_version", "name"):
                entry[key] = ids[0]
        profiles[name] = entry
    return {"profile": DEFAULT_MODEL_SET, "profiles": profiles}
