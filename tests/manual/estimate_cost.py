"""
Estimates what one message costs, per step, for a plan of a given size.

    windows/Scripts/python.exe tests/manual/estimate_cost.py                       5 actions x 5 subactions, 5 tool actions
    windows/Scripts/python.exe tests/manual/estimate_cost.py --actions=3 --subactions=2 --tools=0
    windows/Scripts/python.exe tests/manual/estimate_cost.py --write               save docs/cost_of_a_full_plan.md

Only the default size is saved by --write. The model per step comes from the table of the strongest models
(config/gemini_models.json), and from gemini-3.1-pro-preview on every step, and from gemini-2.5-flash for comparison.
It is an estimate: read the assumptions in the output.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.chdir(ROOT)

from cost_estimate import markdown
from model_table import load_models

DOC_PATH = os.path.join(ROOT, "docs", "cost_of_a_full_plan.md")


def option(argv, name, default):
    value = next((a.split("=", 1)[1] for a in argv if a.startswith(name + "=")), None)
    return int(value) if value is not None else default


def main(argv):
    actions, subactions, tools = option(argv, "--actions", 5), option(argv, "--subactions", 5), option(argv, "--tools", 5)
    if not 1 <= subactions <= 10:
        sys.exit("--subactions must be between 1 and 10 (the limit of the agent)")
    text = markdown(load_models(), actions, subactions, tools)

    if "--write" in argv:
        with open(DOC_PATH, "w", encoding="utf-8", newline="\n") as f:
            f.write(markdown(load_models()))
        print(f"written: {DOC_PATH}")
    else:
        print(text)


main(sys.argv[1:])
