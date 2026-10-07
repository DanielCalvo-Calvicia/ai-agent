"""
Stops in a debugger while the REAL steps of the pipeline run (nothing of the real code is changed).
The LLM is the scripted one of the tests, or the real one with --real (it costs money).

    windows/Scripts/python.exe tests/manual/debug_break.py [--at=start,response,loaded] [--step=NAME] [--real]
                                                           [--message="..."] [--scenario=NAME]

Where it stops (`--at`, default all three):
    start     a step is about to run.                              `state` is what the step received.
    response  an LLM answer just became a `Response`, and is NOT in the state yet.
                                                                   `payload` = the request, `response` = the object,
                                                                   `response.raw` = the JSON the LLM answered.
    loaded    the answer was loaded into the state (for the action executor: after each action got its output
              or error, `action` is that action).                  `state` is the completed object.
Only for one step: --step=project_manager   (see the names with: debug_flow.py --steps)

In the debugger (pdb): `pp snapshot(state)` shows the whole flow object, `pp response_plain(response)` the Response,
`pp payload.message.content` the request, `c` continues to the next stop, `q` quits.
In an IDE (VS Code, PyCharm): run this script under the debugger. `breakpoint()` stops there and you get the
variable panel. To debug your own code instead of a stop, put breakpoints in the real code (see docs/guides/debugging_the_flow.md).
Set PYTHONBREAKPOINT=0 to run without stopping.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.chdir(ROOT)

from flow_trace import STOP_POINTS, response_plain, run_with_stops, snapshot, step_names, to_plain  # noqa: F401  (used in pdb)
from test_flow_golden import MCP_LIST, SCENARIOS, ScriptedLLM


def option(argv, name):
    return next((a.split("=", 1)[1] for a in argv if a.startswith(name + "=")), None)


def main(argv):
    real = "--real" in argv
    scenario = SCENARIOS[option(argv, "--scenario") or "full_path_with_mcp"]
    message = option(argv, "--message") or scenario["message"]
    at = tuple((option(argv, "--at") or ",".join(STOP_POINTS)).split(","))
    steps = option(argv, "--step")
    steps = steps.split(",") if steps else None

    if real:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ROOT, ".env"), override=False)
        from infrastructure.outbound.llm.config import VercelAIConfig
        from infrastructure.outbound.llm.vercel import VercelAIAdapter
        llm, mcp_list = VercelAIAdapter(Config=VercelAIConfig.from_env()), []
    else:
        llm, mcp_list = ScriptedLLM(**scenario["llm"]), MCP_LIST

    for name in steps or []:
        if name not in step_names(mcp_list):
            sys.exit(f"unknown step {name!r}; the steps are: {', '.join(step_names(mcp_list))}")

    print(f"Message: {message!r}   stops: {', '.join(at)}   steps: {', '.join(steps) if steps else 'all'}")
    result = run_with_stops(message, llm, mcp_list, at=at, steps=steps)
    print(f"\nFinished. Reply: {result.reply!r}")


main(sys.argv[1:])
