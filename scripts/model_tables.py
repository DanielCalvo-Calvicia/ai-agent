"""
Shows which model answers each step of each profile (nothing is sent to a provider) and writes the generated documents.
(Moved from tests/manual/show_models.py in T-05.17; for one profile in full: `python scripts/check_agent.py --explain <profile>`.)

    python scripts/model_tables.py                 the models of every profile (flow, model set, the model of each step)
    python scripts/model_tables.py --step=<step>   the options of one step, with price and rating, and what each profile uses
    python scripts/model_tables.py --profiles      writes docs/models/profiles.md: one table per profile, from the assembled profile
    python scripts/model_tables.py --write         writes docs/models/gemini_models_per_step.md
    python scripts/model_tables.py --budget        writes docs/models/models_per_step_budget.md
    python scripts/model_tables.py --table         prints the table of models instead of writing it

The models of a step are in the model sets of model_sets/ (an ordered list per step: the first answers, the next ones are
the fallback) and in the profiles. Change them by editing those files; no environment variable chooses a model.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"), override=False)

from composition_root.environment import install_environment
install_environment()          # the application reads no file and no environment variable itself: it is given them
from application.assembly.assemble import assemble
from application.assembly.config_snapshot import build_snapshot
from application.runtime.step.model_selection import STEP_NAMES
from budget_table import DOC_PATH as BUDGET_DOC_PATH
from budget_table import combined, load_budget, markdown as budget_markdown, read as read_json, MEASURED_PATH
from infrastructure.outbound.config.file_source import FileConfigSource
from infrastructure.outbound.mcp.config.loader import SUPPORTED_TYPES, load_mcp_configs
from model_table import DOC_PATH, blended, load_models, markdown, per_call, read_config, _money
from profile_tables import DOC_PATH as PROFILES_DOC_PATH, explain, profiles_markdown


def option(argv, name):
    return next((a.split("=", 1)[1] for a in argv if a.startswith(name + "=")), None)


def load_agent():
    agent = assemble(build_snapshot(FileConfigSource(ROOT)))
    agent.raise_on_errors()
    servers = [s["name"] for s in load_mcp_configs(os.path.join(ROOT, "mcps")) if s["type"] in SUPPORTED_TYPES]
    return agent, servers


def in_use(agent):
    """step -> [(profile, first model, where it comes from)] for every profile that runs the step."""
    used = {}
    for name in sorted(agent.profiles):
        for row in explain(agent, name, [], models={})["rows"]:
            if row["models"]:
                used.setdefault(row["step"], []).append((name, row["models"][0], row["source"]))
    return used


def show_step(step, data):
    if step not in STEP_NAMES:
        sys.exit(f"unknown step {step!r}. Steps: {', '.join(STEP_NAMES)}")
    info = data["step_tokens"][step]
    used = in_use(load_agent()[0]).get(step, [])
    now = {model for _, model, _ in used}
    print(f"{step}: {data['steps'][step]}\n")
    print(f"About {info['tokens']:,} tokens per call ({info['note']}). Calls per message: {info['calls']}.")
    print("Used by: " + (", ".join(f"{profile} -> {model}" for profile, model, _ in used) or "no profile") + "\n")
    print(f"{'model id':<26}{'in $/1M':>8}{'out $/1M':>9}{'$/call':>10}{'$/1000':>9}  {'rating':<7} why")
    for m in data["models"]:
        level, why = m["ratings"][step]
        mark = "*" if m["id"] in now else " "
        cost = per_call(m, info["tokens"])
        print(f"{mark}{m['id']:<25}{m['input']:>8.2f}{m['output']:>9.2f}{_money(cost):>10}{_money(cost * 1000, 2):>9}  "
              f"{level:<7} {why}")
    print(f"\n* = used by a profile now. To choose: write it in the entry of {step} of a model set (model_sets/<name>.json) "
          "or in `overrides` of a profile.")


def main(argv):
    data = load_models()

    if option(argv, "--step"):
        show_step(option(argv, "--step"), data)
        return

    if "--profiles" in argv:
        agent, servers = load_agent()
        with open(PROFILES_DOC_PATH, "w", encoding="utf-8", newline="\n") as f:
            f.write(profiles_markdown(agent, servers))
        print(f"written: {PROFILES_DOC_PATH}")
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

    agent, _ = load_agent()
    prices = {m["id"]: m for m in data["models"]}
    for name in sorted(agent.profiles):
        profile = agent.profile(name)
        print(f"\nprofile {name}: flow {profile.flow_name or '(its own steps)'}, models {profile.definition.get('models')}")
        print(f"  {'step':<28}{'model':<26}{'in $/1M':>9}{'out $/1M':>10}{'blended':>9}   comes from")
        for row in explain(agent, name, [], models={})["rows"]:
            if not row["models"]:
                continue
            m = prices.get(row["models"][0])
            cost = f"{m['input']:>9.2f}{m['output']:>10.2f}{blended(m):>9.2f}" if m else f"{'?':>9}{'?':>10}{'?':>9}"
            print(f"  {row['step']:<28}{row['models'][0]:<26}{cost}   {row['source']}")
    print("\n? = not in config/gemini_models.json (another provider, or a model that is not in the table)")
    print("Options of one step: model_tables.py --step=<step>; one profile in full: check_agent.py --explain <profile>")


main(sys.argv[1:])
