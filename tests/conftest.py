# tests/manual holds scripts that call real services (LLM, MCP servers). pytest must not run them.
collect_ignore_glob = ["manual/*"]

import os

import pytest


@pytest.fixture(autouse=True)
def _no_model_config_file(monkeypatch, tmp_path_factory):
    """
    The tests expect the default models of the code. config/step_models.json (what the owner chose for
    each step) must not change them, so every test starts without a config file. The tests of the config
    itself point AI_AGENT_MODELS_FILE to their own file.
    """
    monkeypatch.setenv("AI_AGENT_MODELS_FILE", os.path.join(str(tmp_path_factory.getbasetemp()), "no_such_step_models.json"))
    monkeypatch.delenv("AI_AGENT_PARALLEL_ACTIONS", raising=False)
    for phase in list(range(1, 10)) + [99]:
        monkeypatch.delenv(f"AI_AGENT_MODEL_PHASE_{phase}", raising=False)
