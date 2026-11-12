"""
The folders of `infrastructure/outbound/llm/` (2026-11-12): `vercel/` is the only code that imports `ai_sdk`;
`shared/` (providers, tools, schemas) must not.
"""
import ast
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LLM = os.path.join(ROOT, "infrastructure", "outbound", "llm")


def _files(folder):
    for base, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(base, name)


def _imports_sdk(path):
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    for node in ast.walk(tree):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
        if any(n == "ai_sdk" or n.startswith("ai_sdk.") for n in names):
            return True
    return False


def test_shared_never_imports_the_sdk():
    offenders = [os.path.relpath(p, ROOT) for p in _files(os.path.join(LLM, "shared")) if _imports_sdk(p)]
    assert offenders == []


def test_only_the_vercel_folder_imports_the_sdk():
    vercel = os.path.join(LLM, "vercel") + os.sep
    offenders = [os.path.relpath(p, ROOT) for p in _files(LLM) if _imports_sdk(p) and not p.startswith(vercel)]
    assert offenders == []


def test_old_files_are_gone():
    for name in ("vercel.py", "config.py", "provider_models.py", "tools.py", "anthropic_schema.py"):
        assert not os.path.exists(os.path.join(LLM, name)), name
