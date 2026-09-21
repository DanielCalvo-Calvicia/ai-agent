"""
Shows which LLM each step uses, the options and their cost, and lets you choose the model of a step.

    windows/Scripts/python.exe tests/manual/show_models.py                      what every step uses now, with its price
    windows/Scripts/python.exe tests/manual/show_models.py --step=project_manager
                                                                                 every model for that step: cost per call
                                                                                 and how it should perform (cheapest first)
    windows/Scripts/python.exe tests/manual/show_models.py --set=project_manager=gemini-3.8-flash
    windows/Scripts/python.exe tests/manual/show_models.py --clear=project_manager     the profile decides again
    windows/Scripts/python.exe tests/manual/show_models.py --profile=budget           every step at once (proven, budget, balanced, quality)
    windows/Scripts/python.exe tests/manual/show_models.py --write                    rewrite docs/gemini_models_per_step.md
    windows/Scripts/python.exe tests/manual/show_models.py --table                    print that document on the console
    windows/Scripts/python.exe tests/manual/show_models.py --budget                   rewrite docs/models_per_step_budget.md
                                                                                       (all providers, against config/budget.json)

--set, --clear and --profile change config/step_models.json (a typo in a step or a model is refused).
You can also edit that file by hand, or use AI_AGENT_MODEL_PHASE_<n> for one run.
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"), override=False)

from application.orchestration.model_selection import STEP_NAMES, effective_models, models_file
from budget_table import DOC_PATH as BUDGET_DOC_PATH
from budget_table import combined, load_budget, markdown as budget_markdown, read as read_json, MEASURED_PATH
from model_table import (CONFIG_PATH, DOC_PATH, blended, load_models, markdown, per_call, read_config, set_profile,
                         set_step, _money)


def option(argv, name):
    return next((a.split("=", 1)[1] for a in argv if a.startswith(name + "=")), None)


def show_step(step, data):
    if step not in STEP_NAMES:
        sys.exit(f"unknown step {step!r}. Steps: {', '.join(STEP_NAMES)}")
    info = data["step_tokens"][step]
    now = effective_models()[step]
    print(f"{step}: {data['steps'][step]}\n")
    print(f"About {info['tokens']:,} tokens per call ({info['note']}). Calls per message: {info['calls']}.")
    print(f"Uses now: {now[0]}   (from: {now[1]})\n")
    print(f"{'model id':<26}{'in $/1M':>8}{'out $/1M':>9}{'$/call':>10}{'$/1000':>9}  {'rating':<7} why")
    for m in data["models"]:
        level, why = m["ratings"][step]
        mark = "*" if m["id"] == now[0] else " "
        cost = per_call(m, info["tokens"])
        print(f"{mark}{m['id']:<25}{m['input']:>8.2f}{m['output']:>9.2f}{_money(cost):>10}{_money(cost * 1000, 2):>9}  "
              f"{level:<7} {why}")
    print("\n* = in use now.   To choose: show_models.py --set=" + f"{step}=<model id>")


def main(argv):
    data = load_models()

    for step in [a.split("=", 1)[1] for a in argv if a.startswith("--clear=")]:
        set_step(step, None)
        print(f"{step}: the choice was cleared, the profile decides")
    for pair in [a.split("=", 1)[1] for a in argv if a.startswith("--set=")]:
        step, _, model = pair.partition("=")
        try:
            set_step(step, model)
        except ValueError as error:
            sys.exit(f"not changed: {error}")
        print(f"{step}: now {model}")
    if option(argv, "--profile"):
        try:
            set_profile(option(argv, "--profile"))
        except ValueError as error:
            sys.exit(f"not changed: {error}")
        print(f"profile: now {option(argv, '--profile')}")

    if option(argv, "--step"):
        show_step(option(argv, "--step"), data)
        return

    if "--budget" in argv:
        text = budget_markdown(combined(), read_config(), load_budget(), read_json(MEASURED_PATH))
        with open(BUDGET_DOC_PATH, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"written: {BUDGET_DOC_PATH}")
        return

    if "--write" in argv or "--table" in argv:
        text = markdown(data, read_config())
        if "--write" in argv:
            with open(DOC_PATH, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            print(f"written: {DOC_PATH}")
        else:
            print(text)
        return

    prices = {m["id"]: m for m in data["models"]}
    print(f"Config file: {models_file()}\n")
    print(f"{'step':<28}{'model':<26}{'in $/1M':>9}{'out $/1M':>10}{'blended':>9}   comes from")
    for step, (model_id, source) in effective_models().items():
        m = prices.get(model_id)
        cost = f"{m['input']:>9.2f}{m['output']:>10.2f}{blended(m):>9.2f}" if m else f"{'?':>9}{'?':>10}{'?':>9}"
        print(f"{step:<28}{model_id:<26}{cost}   {source}")
    print("\n? = not in config/gemini_models.json (another provider, or a model that is not in the table)")
    print("Options of one step: show_models.py --step=<step>")


main(sys.argv[1:])
