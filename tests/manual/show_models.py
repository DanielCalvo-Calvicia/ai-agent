"""
MANUAL tool: shows which model answers each step (nothing is sent to a provider) and writes the generated documents.

    python tests/manual/show_models.py                 the model of every step and what it costs
    python tests/manual/show_models.py --step=<step>   the options of one step, with price and rating
    python tests/manual/show_models.py --write         writes docs/models/gemini_models_per_step.md
    python tests/manual/show_models.py --budget        writes docs/models/models_per_step_budget.md
    python tests/manual/show_models.py --table         prints the table of models instead of writing it

The models of a step are in the model sets of model_sets/ (an ordered list per step: the first answers, the next ones are
the fallback) and in the profiles. Change them by editing those files; no environment variable chooses a model.
This tool shows the model set the service runs on until profiles choose theirs (T-05.5).
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"), override=False)

from application.engine.support.model_selection import DEFAULT_MODEL_SET, STEP_NAMES, ModelResolver, effective_models
from budget_table import DOC_PATH as BUDGET_DOC_PATH
from budget_table import combined, load_budget, markdown as budget_markdown, read as read_json, MEASURED_PATH
from model_table import DOC_PATH, MODEL_SETS_DIR, blended, load_models, markdown, per_call, read_config, read_model_sets, _money


def option(argv, name):
    return next((a.split("=", 1)[1] for a in argv if a.startswith(name + "=")), None)


def in_use():
    return effective_models(ModelResolver({"models": DEFAULT_MODEL_SET}, read_model_sets()))


def show_step(step, data):
    if step not in STEP_NAMES:
        sys.exit(f"unknown step {step!r}. Steps: {', '.join(STEP_NAMES)}")
    info = data["step_tokens"][step]
    now = in_use()[step]
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
    print(f"\n* = in use now. To choose: write it in the entry of {step} of a model set (model_sets/<name>.json).")


def main(argv):
    data = load_models()

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
    print(f"Model set in use: {DEFAULT_MODEL_SET} ({MODEL_SETS_DIR})\n")
    print(f"{'step':<28}{'model':<26}{'in $/1M':>9}{'out $/1M':>10}{'blended':>9}   comes from")
    for step, (model_id, source) in in_use().items():
        m = prices.get(model_id)
        cost = f"{m['input']:>9.2f}{m['output']:>10.2f}{blended(m):>9.2f}" if m else f"{'?':>9}{'?':>10}{'?':>9}"
        print(f"{step:<28}{model_id:<26}{cost}   {source}")
    print("\n? = not in config/gemini_models.json (another provider, or a model that is not in the table)")
    print("Options of one step: show_models.py --step=<step>")


main(sys.argv[1:])
