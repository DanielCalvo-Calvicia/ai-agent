"""
Checks the whole agent: reads the profiles, flows, step declarations, model sets and the catalog of fields, and assembles them
(application/assembly/assemble.py). Strict: every problem is printed, with its file and key, and the exit code is 1 if there is any.
It reads files only: no model is called and no server is reached.

    python scripts/check_agent.py                 the repository
    python scripts/check_agent.py --root <dir>    another folder with the same layout (profiles/, flows/, ...)
    python scripts/check_agent.py --explain <profile>   what the assembled profile is made of: the steps in order, the model of each
                                                  and where it comes from, the tools, the prompts, the hash and the cost of a full plan

Run it before a pull request that adds or changes a profile: the service itself only disables a wrong profile.
"""
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tests"))          # profile_tables.py (--explain)

from application.assembly.assemble import assemble
from application.assembly.config_snapshot import build_snapshot
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

    if "--explain" in argv:
        name = argv[argv.index("--explain") + 1] if argv.index("--explain") + 1 < len(argv) else ""
        if name not in agent.profiles:
            print(f"error: no profile {name!r}. Profiles: {', '.join(sorted(agent.profiles))}")
            return 1
        from profile_tables import explain, explain_text
        from infrastructure.outbound.mcp.config import SUPPORTED_TYPES, load_mcp_configs
        servers = [s["name"] for s in load_mcp_configs(os.path.join(root, "mcps")) if s["type"] in SUPPORTED_TYPES]    # the ones the agent can use
        print(explain_text(explain(agent, name, servers)))
        return 0

    print(f"ok: {len(agent.profiles)} profile(s), {len(snapshot.flows)} flow(s), {len(snapshot.step_defs)} step declaration(s), "
          f"{len(snapshot.model_sets)} model set(s), {len(snapshot.state_fields)} field(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
