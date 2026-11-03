"""
Checks the whole agent: reads the profiles, flows, step declarations, model sets and the catalog of fields, and assembles them
(application/engine/assemble.py). Strict: every problem is printed, with its file and key, and the exit code is 1 if there is any.
It reads files only: no model is called and no server is reached.

    python scripts/check_agent.py                 the repository
    python scripts/check_agent.py --root <dir>    another folder with the same layout (profiles/, flows/, ...)

Run it before a pull request that adds or changes a profile: the service itself only disables a wrong profile.
"""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, PROJECT_ROOT)

from application.engine.assemble import assemble
from application.engine.config_snapshot import build_snapshot
from infrastructure.outbound.config.file_source import FileConfigSource
from infrastructure.outbound.llm.anthropic_schema import anthropic_schema_problems
from infrastructure.outbound.mcp.config import load_tool_snapshot


def main(argv) -> int:
    root = argv[argv.index("--root") + 1] if "--root" in argv else PROJECT_ROOT
    snapshot = build_snapshot(FileConfigSource(root))
    agent = assemble(
        snapshot,
        mcp_servers=load_tool_snapshot(os.path.join(root, "mcps")),
        schema_rules={"anthropic": anthropic_schema_problems},
    )

    problems = agent.all_problems()
    for problem in problems:
        print(f"error: {problem}")
    if problems:
        print(f"\n{len(problems)} problem(s) in {len(agent.problems)} file(s); {len(agent.profiles)} profile(s) are fine")
        return 1

    print(f"ok: {len(agent.profiles)} profile(s), {len(snapshot.flows)} flow(s), {len(snapshot.step_defs)} step declaration(s), "
          f"{len(snapshot.model_sets)} model set(s), {len(snapshot.state_fields)} field(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
