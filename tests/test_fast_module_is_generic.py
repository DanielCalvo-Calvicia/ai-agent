"""T-08.6 (ADR-019): the fast tool path names no MCP server and no tool. What one server means goes in the profile's prompt appends."""
import glob
import json
import os
import re

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _names() -> set:
    """The servers of `mcps/` (a file maps a server name to its settings) and every tool they allow or use for jobs."""
    names = set()
    for path in glob.glob(os.path.join(PROJECT_ROOT, "mcps", "*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for name, server in data.items():
            if name.startswith("_") or not isinstance(server, dict):
                continue
            names.add(name)
            names.update(server.get("allowed_tools", []))
            names.update(v for k, v in server.items() if k in ("job_read_tool", "job_cancel_tool"))
            names.update(server.get("job_recall_tools", []))
    return {n for n in names if n and len(n) > 4}


def _generic_files() -> list:
    root = PROJECT_ROOT
    files = glob.glob(os.path.join(root, "application", "runtime", "step", "library", "fast", "*.py"))
    files += [os.path.join(root, "application", "support", "tools", "direct_call.py"), os.path.join(root, "flows", "fast.json")]
    files += [os.path.join(root, "step_defs", f"{n}.json") for n in ("tool_selector", "tool_caller", "answer_writer")]
    files += [os.path.join(root, "prompts", "50_tool_selector.txt"), os.path.join(root, "prompts", "51_answer_writer.txt")]
    return files


def test_there_are_names_to_look_for():
    names = _names()
    assert "dynamics_microservice" in names and "customer_orders" in names


def test_no_generic_file_of_the_fast_path_names_a_server_or_a_tool():
    names, found = _names(), []
    for path in _generic_files():
        assert os.path.isfile(path), path
        with open(path, encoding="utf-8") as f:
            text = f.read()
        found += [(os.path.basename(path), n) for n in names if re.search(r"(?<![A-Za-z0-9_])" + re.escape(n) + r"(?![A-Za-z0-9_])", text)]
    assert found == []
