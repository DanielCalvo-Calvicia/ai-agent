import os
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class VercelAIConfig:
    """Immutable configuration of the LLM adapter: provider keys, endpoints and the MCP tool executor."""

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    mistral_api_key: str = ""
    groq_api_key: str = ""
    cohere_api_key: str = ""
    github_api_key: str = ""
    # Base URLs of the OpenAI-compatible endpoints.
    google_url: str = ""
    mistral_url: str = ""
    groq_url: str = ""
    cohere_url: str = ""
    github_url: str = ""
    OLLAMA_URL: str = ""
    tool_executor: Optional[Any] = None

    @classmethod
    def from_env(cls, tool_executor: Optional[Any] = None) -> "VercelAIConfig":
        """
        Reads the settings from the process environment when it is called
        (not at import time), so a .env loaded at startup is respected.
        """
        env = os.environ.get
        return cls(
            openai_api_key=env("OPENAI_API_KEY", ""),
            anthropic_api_key=env("ANTHROPIC_API_KEY", ""),
            google_api_key=env("GOOGLE_API_KEY", ""),
            mistral_api_key=env("MISTRAL_API_KEY", ""),
            groq_api_key=env("GROQ_API_KEY", ""),
            cohere_api_key=env("COHERE_API_KEY", ""),
            github_api_key=env("GITHUB_PAT", "") or env("GITHUB_API_KEY", ""),
            google_url=env("GOOGLE_URL", ""),
            mistral_url=env("MISTRAL_URL", ""),
            groq_url=env("GROQ_URL", ""),
            cohere_url=env("COHERE_URL", ""),
            github_url=env("GITHUB_URL", ""),
            OLLAMA_URL=env("OLLAMA_URL", ""),
            tool_executor=tool_executor,
        )
