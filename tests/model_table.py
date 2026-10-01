"""
Builds the tables of Gemini models (docs/gemini_models_per_step.md) from config/gemini_models.json, the one
place where prices and ratings are kept, and writes the choice of a model per step to config/step_models.json.
`python tests/manual/show_models.py` shows and changes it.
"""
import json
import os
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MODELS_PATH = os.path.join(PROJECT_ROOT, "config", "gemini_models.json")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "step_models.json")
DOC_PATH = os.path.join(PROJECT_ROOT, "docs", "gemini_models_per_step.md")

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
    chosen = config.get("steps", {}) or {}
    active_profile = profiles.get(active, {})

    def in_use(step: str) -> str:
        return chosen.get(step) or active_profile.get(step) or active_profile.get("default") or "(code default)"

    lines = [
        "# Gemini models for each step",
        "",
        "_Generated from `config/gemini_models.json` by `tests/manual/show_models.py --write`. Edit that file, not this one._",
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
        "To use a model for a step, put its id in `steps` of `config/step_models.json`, or run "
        "`windows\\Scripts\\python.exe tests\\manual\\show_models.py --set=<step>=<model id>`. "
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
                f"`\"{name}\": \"{model['id']}\"` |")

    lines += ["", "## 4. Profiles in `config/step_models.json`", "",
              f"Active profile: **{active}**. `steps` wins over the profile, and `AI_AGENT_MODEL_PHASE_<n>` wins over both.",
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
              "`windows\\Scripts\\python.exe tests\\manual\\show_models.py --step=project_manager`.",
              "2. Choose: `windows\\Scripts\\python.exe tests\\manual\\show_models.py --set=project_manager=gemini-3.8-flash` "
              "(or write it in `steps` of `config/step_models.json`). To go back to the profile: `--clear=project_manager`. "
              "To change every step at once: `--profile=budget` (or `balanced`, `quality`, `proven`).",
              "3. For one run only: the variable `AI_AGENT_MODEL_PHASE_<n>` (n: 1 triage, 2 planner, 3 gate, 4 worker, "
              "5 tools, 6 cleaning, 7 draft, 8 editor, 9 answer checker, 99 question).",
              "4. Try the model on that step before you trust it: run the flow once with "
              "`tests/manual/debug_flow.py --real`, then repeat the step with `--only=<step> --state=<file> --repeat=5`. "
              "The problems it finds and `compare.md` show if the model is steady.",
              ""]
    return "\n".join(lines)


# ===============================================
#  WRITING THE CHOICE
# ===============================================

def read_config(path: str = CONFIG_PATH) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_config(config: Dict[str, Any], path: str = CONFIG_PATH) -> None:
    """Checks the config (unknown step, model or profile fail) and only then writes it."""
    import tempfile
    from application.orchestration.support.model_selection import _check

    _check(config, path)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", delete=False, dir=os.path.dirname(path),
                                     suffix=".tmp") as tmp:
        tmp.write(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp.name, path)


def set_step(step: str, model_id: Optional[str], path: str = CONFIG_PATH) -> Dict[str, Any]:
    """Chooses `model_id` for `step` (None clears the choice, so the profile applies again)."""
    from application.orchestration.support.model_selection import STEP_NAMES

    if step not in STEP_NAMES:
        raise ValueError(f"unknown step {step!r}. Steps: {', '.join(STEP_NAMES)}")
    config = read_config(path)
    config.setdefault("steps", {})[step] = model_id
    write_config(config, path)
    return config


def set_profile(profile: str, path: str = CONFIG_PATH) -> Dict[str, Any]:
    config = read_config(path)
    config["profile"] = profile
    write_config(config, path)
    return config
