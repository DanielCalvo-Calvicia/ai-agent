# tests/manual holds scripts that call real services (LLM, MCP servers). pytest must not run them.
collect_ignore_glob = ["manual/*"]

import pytest


@pytest.fixture(autouse=True)
def _defaults_of_the_code(monkeypatch):
    """
    The tests expect the default models of the code: a PhaseRunner built without a ModelResolver uses the DEFAULT_MODEL of
    each step, whatever the model sets of model_sets/ say. The tests of the model sets build their own ModelResolver.
    """
    monkeypatch.delenv("AI_AGENT_PARALLEL_ACTIONS", raising=False)
    monkeypatch.setenv("AI_AGENT_RETRY_WAIT_SECONDS", "0")      # no waiting between the tries of a failed call (tests/test_fallback.py sets its own)


@pytest.fixture(autouse=True)
def _no_gestures(monkeypatch):
    """
    The arm gesture that goes with a reply is its own feature (tests/test_expression.py): it adds a model call after the
    conversation and special flows, so every other test starts with it off. The tests of the feature turn it on.
    """
    monkeypatch.setenv("AI_AGENT_EXPRESSION", "0")
    monkeypatch.delenv("AI_AGENT_EXPRESSION_SEED", raising=False)
    monkeypatch.delenv("AI_AGENT_SPEECH_CHARS_PER_SECOND", raising=False)
