"""
Builds docs/models_per_step_budget.md: the models of every provider, per step, with what they cost against a monthly
budget (config/budget.json). Prices and ratings: config/gemini_models.json and config/other_models.json.
`python tests/manual/show_models.py --budget` writes the document.
"""
import json
import os
from typing import Any, Dict, List

from cost_estimate import THINKING_FACTOR, StepUsage, price, rows_for, total_row, usage
from model_table import CONFIG_PATH, PROJECT_ROOT, blended, load_models

OTHER_PATH = os.path.join(PROJECT_ROOT, "config", "other_models.json")
BUDGET_PATH = os.path.join(PROJECT_ROOT, "config", "budget.json")
MEASURED_PATH = os.path.join(PROJECT_ROOT, "config", "measured_runs.json")
DOC_PATH = os.path.join(PROJECT_ROOT, "docs", "models_per_step_budget.md")

LEVEL_WHY = {
    "best": "the right size and price for this step",
    "good": "works well for this step",
    "ok": "works, but weaker, slower or dearer than needed",
    "weak": "likely to give poor results here",
    "avoid": "wasteful here (dearer or slower than the step needs)",
}
PROVIDER_NAMES = {"google": "Google", "groq": "Groq", "openai": "OpenAI", "anthropic": "Anthropic",
                  "mistral": "Mistral", "deepseek": "DeepSeek"}
WORKS_TEXT = {
    "tested": "yes, tested",
    "should work, untested": "should (no key to test)",
    "needs adapter change": "needs adapter change",
    "not available": "no (API refused it)",
}


def read(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_budget() -> Dict[str, Any]:
    return read(BUDGET_PATH)


def budget_usd_per_message(budget: Dict[str, Any]) -> float:
    return budget["eur_per_month"] * budget["usd_per_eur"] / budget["messages_per_month"]


def eur(usd: float, budget: Dict[str, Any]) -> float:
    return usd / budget["usd_per_eur"]


def combined() -> Dict[str, Any]:
    """The models of every provider in one list, cheapest first, with the same shape as gemini_models.json."""
    google, other = load_models(), read(OTHER_PATH)
    models: List[Dict[str, Any]] = []

    for m in google["models"]:
        refused = m["api_check"].startswith("FAILED")
        models.append({**m, "provider": "google", "works_today": "not available" if refused else "tested",
                       "adapter_note": m["api_check"] if refused else "Works today. Answered a test call.",
                       "output_multiplier": 1.0})
    for m in other["models"]:
        models.append({**m, "ratings": {step: [level, LEVEL_WHY[level]] for step, level in m["ratings"].items()},
                       "api_check": m["works_today"], "free_tier": False})

    models.sort(key=blended)
    return {"steps": google["steps"], "step_tokens": google["step_tokens"], "message_tokens": google["message_tokens"],
            "_levels": google["_levels"], "models": models, "_source_other": other["_source"],
            "_works_today": other["_works_today"], "_ratings_other": other["_ratings"]}


def measured_cost(run: Dict[str, Any], prices: Dict[str, Dict[str, Any]]) -> float:
    """USD of one measured message: sent x input price + (answered + thinking) x output price."""
    m = prices[run["id"]]
    return (run["sent"] * m["input"] + (run["answered"] + run["thinking"]) * m["output"]) / 1e6


def profile_choice(data: Dict[str, Any], config: Dict[str, Any], name: str) -> Dict[str, Dict[str, Any]]:
    by_id = {m["id"]: m for m in data["models"]}
    profile = config["profiles"][name]
    return {step: by_id[profile.get(step) or profile["default"]] for step in data["steps"]}


def _usd(value: float) -> str:
    return "$0" if value == 0 else f"${value:.4f}" if value < 0.01 else f"${value:.3f}" if value < 1 else f"${value:.2f}"


def _eur(value: float) -> str:
    return "0" if value == 0 else f"{value:.2f}"


def markdown(data: Dict[str, Any], config: Dict[str, Any], budget: Dict[str, Any], measured: Dict[str, Any]) -> str:
    steps = data["steps"]
    models = data["models"]
    big, small = budget["big_plan"], budget["small_plan"]
    big_usage = usage(big["actions"], big["subactions"], big["tools"])
    small_usage = usage(small["actions"], small["subactions"], small["tools"])
    limit_usd = budget_usd_per_message(budget)
    limit_eur = budget["eur_per_month"] / budget["messages_per_month"]
    prices = {m["id"]: m for m in models}
    nodes = big["actions"] * (1 + big["subactions"])
    active = config.get("profile")

    lines = [
        "# Models for each step, within a budget",
        "",
        "_Generated from `config/gemini_models.json`, `config/other_models.json`, `config/measured_runs.json` and "
        "`config/budget.json` by `tests/manual/show_models.py --budget`. Edit those files, not this one._",
        "",
        "## The budget",
        "",
        f"- **{budget['eur_per_month']} EUR a month at most, for {budget['messages_per_month']:,} messages** = "
        f"{limit_eur:.3f} EUR = **${limit_usd:.4f} per message** ({budget['rate_source']}).",
        f"- The worst case is used: **every message has a big plan of {nodes} actions** ({big['actions']} actions with "
        f"{big['subactions']} subactions each, {big['tools']} of them with a tool). A message with a small plan of "
        f"{small['actions']} actions costs far less, so the real month will be under the budget.",
        f"- {load_models()['_source']}",
        f"- {data['_source_other']}",
        f"- {data['_ratings_other']} Ratings: " + "; ".join(f"**{k}** = {v}" for k, v in data["_levels"].items()) + ".",
        "",
        "## 1. What was measured, and what it changes",
        "",
        "One real message was sent through the whole agent with each model on every step "
        f"(\"{measured['message']}\"). Tokens as the provider counted them; **thinking = total - sent - answered**.",
        "",
        "| Model | Calls | Sent | Answered | Thinking | Cost of that message | Per 1,000 such messages |",
        "|---|---|---|---|---|---|---|",
    ]
    runs = sorted(measured["runs"], key=lambda r: measured_cost(r, prices))
    for r in runs:
        cost = measured_cost(r, prices)
        lines.append(f"| `{r['id']}` | {r['calls']} | {r['sent']:,} | {r['answered']:,} | {r['thinking']:,} | "
                     f"{_usd(cost)} | {_usd(cost * 1000)} = {_eur(eur(cost * 1000, budget))} EUR |")

    lines += [
        "",
        "- **Thinking is billed, and the API hides it.** `gemini-2.5-flash` thought 2,484 tokens for 3,194 answered "
        "(44% more output) and `gemini-3.8-flash` 3,611 for 2,357 (150% more). Google's `completion_tokens` does not include "
        "them; only `total_tokens` does. The two lite models thought nothing. This is why the Flash models cost 4 to 14 times "
        "more than the lite ones on the same message.",
        "- `openai/gpt-oss` (Groq) is a reasoning model too, but its reasoning is inside the counted output tokens "
        "(about 2.5 times the visible answer, measured), and its price is low: it cost about the same as the lite models.",
        "- A switch exists to turn thinking off: with `reasoning_effort=\"none\"` `gemini-2.5-flash` thought 0 tokens instead of 411 on a "
        "test question (tested with a direct call). The agent does not send it yet, so a thinking model is still billed for thinking.",
        "",
        "## 2. Profiles and their cost",
        "",
        f"Cost of one message, thinking included. The limit is **${limit_usd:.4f} ({limit_eur:.3f} EUR)**. "
        f"Big plan = {nodes} actions; small plan = {small['actions']} actions.",
        "",
        "| Profile | Big plan, USD | Big plan, EUR per 1,000 messages | Fits the budget? | Small plan, USD | Providers | Active |",
        "|---|---|---|---|---|---|---|",
    ]

    strongest = {}
    from cost_estimate import choice_strongest
    candidates = [("strongest (per step, from the earlier table)", choice_strongest(data))]
    candidates += [(name, profile_choice(data, config, name)) for name in config["profiles"]]
    for name, choice in candidates:
        big_total = total_row(rows_for(choice, big_usage))["thinking"]
        small_total = total_row(rows_for(choice, small_usage))["thinking"]
        providers = ", ".join(sorted({PROVIDER_NAMES[c["provider"]] for c in choice.values()}))
        fits = "**yes**" if big_total <= limit_usd else "no"
        lines.append(f"| {name} | {_usd(big_total)} | {_eur(eur(big_total * 1000, budget))} | {fits} | {_usd(small_total)} | "
                     f"{providers} | {'yes' if name == active else ''} |")

    lines += ["", "### What each step uses in the profiles that fit, and what it costs (big plan)", ""]
    fitting = [n for n, c in candidates if n in config["profiles"]
               and total_row(rows_for(c, big_usage))["thinking"] <= limit_usd]
    for name in fitting:
        choice = dict(candidates)[name]
        rows = rows_for(choice, big_usage)
        total = total_row(rows)
        lines += [f"**{name}**", "", "| Step | Model | Calls | Cost (thinking included) |", "|---|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['step']} | `{r['model']}` | {r['calls']} | {_usd(r['thinking'])} |")
        lines += [f"| **Total** | | {sum(u.calls for u in big_usage)} | **{_usd(total['thinking'])}** "
                  f"= {_eur(eur(total['thinking'] * 1000, budget))} EUR per 1,000 messages |", ""]
        if "_about" in config["profiles"][name]:
            lines += [config["profiles"][name]["_about"], ""]

    lines += [
        "To use one: `windows\\Scripts\\python.exe tests\\manual\\show_models.py --profile=budget50` "
        "(then `--step=<step>` and `--set=<step>=<model id>` to change a step).",
        "",
        "## 3. All the models, cheapest first",
        "",
        "`Works today`: **yes, tested** = run end to end through this agent with this project's key, 0 problems; "
        "**should (no key to test)** = the API accepts what the agent sends, but there is no key in `.env`; "
        "**needs adapter change** = the agent would have to change first (see the note under the table).",
        "",
        "| # | Name | Provider | Model id | In $/1M | Out $/1M | Blended $/1M | Works today | Reasoning |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for number, m in enumerate(models, 1):
        star = "*" if m["price_note"] else ""
        lines.append(f"| {number} | {m['name']} | {PROVIDER_NAMES[m['provider']]} | `{m['id']}` | {m['input']:.3f} | "
                     f"{m['output']:.2f}{star} | {blended(m):.2f} | {WORKS_TEXT[m['works_today']]} | {m['thinking']} |")
    lines += ["", *[f"\\* {m['name']}: {m['price_note']}" for m in models if m["price_note"]], "",
              "Notes on what each model needs:", ""]
    lines += [f"- `{m['id']}`: {m['adapter_note']}" for m in models if m["works_today"] != "tested"]

    lines += ["", "## 4. One table per step", "",
              "Each table lists the models rated better than **avoid** for the step, cheapest first. "
              "`Cost of the step` is what all the calls of that step cost in one message with the big plan, thinking included. "
              "`Per 1,000 messages` is the same in EUR.", ""]
    for step, need in steps.items():
        u = next(x for x in big_usage if x.step == step)
        info = data["step_tokens"][step]
        lines += [f"### {step}", "", need, "",
                  f"Big plan: {u.calls} call(s), {u.input_tokens:,} tokens sent and {u.output_tokens:,} answered "
                  f"(measured per call with gemini-2.5-flash: {info['tokens']:,} tokens; {info['note']}).", "",
                  "| Model | Provider | Model id | In $/1M | Out $/1M | Cost of the step | EUR per 1,000 messages | Works today | Rating | Use it |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for m in models:
            level = m["ratings"][step][0]
            if level == "avoid":
                continue
            cost = price(m, u, True)
            lines.append(f"| {m['name']} | {PROVIDER_NAMES[m['provider']]} | `{m['id']}` | {m['input']:.3f} | "
                         f"{m['output']:.2f}{'*' if m['price_note'] else ''} | {_usd(cost)} | {_eur(eur(cost * 1000, budget))} | "
                         f"{WORKS_TEXT[m['works_today']]} | **{level}** | `\"{step}\": \"{m['id']}\"` |")
        lines.append("")

    lines += ["## 5. How to choose", "",
              "1. One profile for every step: `windows\\Scripts\\python.exe tests\\manual\\show_models.py --profile=budget50`.",
              "2. One step: `windows\\Scripts\\python.exe tests\\manual\\show_models.py --set=project_manager=openai/gpt-oss-120b` "
              "(or write the line of the table in `steps` of `config/step_models.json`). Only models the agent's provider "
              "table knows can be chosen (`domain/value_objects/model_catalog.py`).",
              "3. See what is in use with its price: `windows\\Scripts\\python.exe tests\\manual\\show_models.py`.",
              "4. Before you trust a model on a step: `tests/manual/debug_flow.py --real`, then `--only=<step> --state=<file> "
              "--repeat=5`. The problems it finds and `compare.md` show if the model is steady.",
              "5. To change the budget, the rate or the size of the plans: `config/budget.json`, then `show_models.py --budget`.",
              ""]
    return "\n".join(lines)
