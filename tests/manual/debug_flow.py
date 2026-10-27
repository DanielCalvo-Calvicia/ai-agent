"""
Debug the execution of each part of the agent. It runs the REAL steps of the pipeline and saves
what happened to files (nothing is printed unless you ask). Only the LLM can be replaced:
the scripted one of the tests (free, offline) or, with --real, the real LLM configured in .env (it costs money).

  1) Follow a whole message, step by step
        windows/Scripts/python.exe tests/manual/debug_flow.py --message="Hello"  [--real]
     Saves in tests/output/debug/<name>/ :
        NN_<step>_phaseN.md   one file per LLM call: the request sent (top), the raw answer, PROBLEMS found in
                              the answer (schema, wrong text), the Response object, what changed, and the
                              full object after the data was loaded (bottom)
        00_index.md, report.md   the list of calls with their problems, and the step-by-step report
        states/NN_<step>.pkl  the state each step RECEIVED (to run that step again alone, see 2)

  2) Run ONE step alone, with exactly the same input, as many times as you want
        windows/Scripts/python.exe tests/manual/debug_flow.py --only=project_manager \\
            --state=tests/output/debug/<name>/states/02_project_manager.pkl --repeat=5 --real
     Saves run_1 ... run_5 (one folder each) and compare.md: for each key of the answer, do the runs agree?

Options:
    --steps          list the steps
    --scenario=NAME  script the LLM with a scenario of the tests (default: full_path_with_mcp; --list to see them)
    --list           list the scenarios
    --message="..."  the message to send
    --real           use the real LLM (needs the keys and models of .env / AI_AGENT_MODEL_PHASE_<n>)
    --only=STEP      run only this step (needs --state)
    --state=PATH     a states/*.pkl file saved by a previous run (only files you saved yourself)
    --repeat=N       with --only: how many times to run the step
    --name=NAME      the folder name under tests/output/debug (default: the scenario or `real`)
    --out=PATH       another output folder
    --print          also print the report on the console
    --interactive    with --print: stop after each step and wait for Enter (q + Enter quits)
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.chdir(ROOT)

from flow_trace import (StopTrace, format_problems, format_step, load_state, save_step_inputs, step_names,
                        trace_flow, trace_step, write_compare, write_markdown_files, write_report)
from test_flow_golden import MCP_LIST, SCENARIOS, ScriptedLLM


def option(argv, name):
    return next((a.split("=", 1)[1] for a in argv if a.startswith(name + "=")), None)


def llm_factory(argv, scenario):
    if "--real" not in argv:
        return lambda: ScriptedLLM(**scenario["llm"])

    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"), override=False)
    from infrastructure.outbound.llm.config import VercelAIConfig
    from infrastructure.outbound.llm.vercel import VercelAIAdapter
    return lambda: VercelAIAdapter(Config=VercelAIConfig.from_env())


def main(argv):
    if "--list" in argv:
        for name, scenario in SCENARIOS.items():
            print(f"{name:<48} {scenario['message']!r}")
        return
    if "--steps" in argv:
        print("\n".join(step_names(MCP_LIST)))
        return

    real = "--real" in argv
    scenario_name = option(argv, "--scenario") or "full_path_with_mcp"
    scenario = SCENARIOS[scenario_name]
    message = option(argv, "--message") or scenario["message"]
    name = option(argv, "--name") or ("real" if real else scenario_name)
    out_dir = option(argv, "--out") or os.path.join(ROOT, "tests", "output", "debug", name)
    new_llm = llm_factory(argv, scenario)
    mcp_list = [] if real else MCP_LIST

    only = option(argv, "--only")
    if only:
        state_path = option(argv, "--state")
        if not state_path:
            sys.exit("--only needs --state=PATH (a states/*.pkl file saved by a previous run)")
        state = load_state(state_path)
        runs, folders = [], []
        for number in range(1, int(option(argv, "--repeat") or 1) + 1):
            mods, after, waiting = trace_step(only, state, new_llm(), mcp_list)
            folder = os.path.join(out_dir, f"only_{only}", f"run_{number}")
            write_markdown_files(mods, folder, f"{only}, run {number}")
            runs.append(mods)
            folders.append(folder)
            problems = sum(len(m.call.problems) for m in mods)
            failed = any(m.call.error for m in mods)
            print(f"run {number}: {len(mods)} LLM calls, {problems} problems, "
                  f"{'FAILED' if failed else 'ok'}, waiting for the user: {waiting}")
        compare = write_compare(runs, os.path.join(out_dir, f"only_{only}", "compare.md"), only)
        print(f"files in {os.path.dirname(compare)}   (compare.md compares the runs)")
        return

    def on_step(trace):
        if "--print" in argv:
            print(format_step(trace), "\n")
            if "--interactive" in argv and input("Enter = next step, q = quit > ").strip().lower() == "q":
                raise StopTrace()

    mods, failures = [], []
    traces = trace_flow(message, new_llm(), mcp_list, on_step, modifications=mods, failures=failures)   # one run
    paths = write_markdown_files(mods, out_dir, name)
    write_report(traces, os.path.join(out_dir, "report.md"), name, mods, failures)
    states = save_step_inputs(traces, out_dir)
    print(f"{len(paths)} LLM calls saved in {out_dir}  ({len(states)} step inputs in states/)")
    print(format_problems(traces, mods, failures))


main(sys.argv[1:])
