from dataclasses import dataclass
from enum import Enum
from typing import Union

# Ids found, with their status, in each provider's own documentation on 2026-10-27 (T-02, docs/proposals/PR-004).
# An id without full information (id, price or status) is not used: it stays below as a comment, with the reason.


class OpenAIModels(str, Enum):
    # GPT-6 and GPT-6.1 (priced in config/other_models.json when it has an entry there)
    GPT_6_ASTRA = "gpt-6-astra"
    GPT_6_1_SOL = "gpt-6.1-sol"
    GPT_6_1_TERRA = "gpt-6.1-terra"
    GPT_6_LUNA = "gpt-6-luna"
    GPT_6_SOL = "gpt-6-sol"
    # GPT-5.6, 5.5, 5.4 and 5.2
    GPT_5_6_SOL = "gpt-5.6-sol"
    GPT_5_6_TERRA = "gpt-5.6-terra"
    GPT_5_6_LUNA = "gpt-5.6-luna"
    GPT_5_5 = "gpt-5.5"
    GPT_5_4 = "gpt-5.4"
    GPT_5_4_MINI = "gpt-5.4-mini"
    GPT_5_4_NANO = "gpt-5.4-nano"  # deprecated, shutdown 2027-04-01
    GPT_5_2 = "gpt-5.2"
    GPT_5_1 = "gpt-5.1"  # deprecated, shutdown 2027-04-01
    # Deprecated, still served until the date
    GPT_5 = "gpt-5"  # shutdown 2026-12-11
    GPT_5_MINI = "gpt-5-mini"  # shutdown 2026-12-11
    GPT_5_NANO = "gpt-5-nano"  # shutdown 2026-12-11
    GPT_4O = "gpt-4o"  # shutdown 2027-01-14
    GPT_4O_MINI = "gpt-4o-mini"  # shutdown 2027-01-14
    O3_MINI = "o3-mini"
    # Not used: the GPT-4.1 family (deprecated, shutdown 2027-01-14; the nano one was shut down on 2026-10-23), the *-pro models, o3 and o3-pro (not needed here)
    # Shut down: o1, o4-mini, gpt-4-turbo (2026-10-23), o1-mini, gpt-4.5-preview (earlier); gpt-5-turbo was never listed

class GoogleModels(str, Enum):
    # Gemini ids of Google's models and pricing pages, 2026-10-27; prices in config/gemini_models.json
    GEMINI_4_ARGON = "gemini-4-argon"  # no free tier; price doubles on 2026-12-01
    GEMINI_3_8_FLASH = "gemini-3.8-flash"  # price doubles on 2027-01-01
    GEMINI_3_6_FLASH = "gemini-3.6-flash"  # price doubles on 2027-01-01
    GEMINI_3_5_FLASH_LITE = "gemini-3.5-flash-lite"
    GEMINI_3_1_FLASH_LITE = "gemini-3.1-flash-lite"
    GEMINI_3_1_PRO_PREVIEW = "gemini-3.1-pro-preview"  # no free tier
    GEMINI_3_FLASH_PREVIEW = "gemini-3-flash-preview"
    # Gemini 2.5 is served only to users who used it before. Refused with this project's key on 2026-10-28 (404, "no longer
    # available to new users"), so not used: gemini-2.5-flash, gemini-2.5-flash-lite
    # Not listed any more: gemini-3.7-flash, gemini-3.5-flash, gemini-1.5-pro, gemini-1.5-flash
    # Refused with this project's key (404, "no longer available to new users"): gemini-2.5-pro

class AnthropicModels(str, Enum):
    # Current (Anthropic's models overview, 2026-10-27; every id is its own pinned snapshot)
    CLAUDE_FABLE_5_1 = "claude-fable-5-1"
    CLAUDE_OPUS_5_5 = "claude-opus-5-5"
    CLAUDE_SONNET_5_5 = "claude-sonnet-5-5"
    CLAUDE_HAIKU_5_5 = "claude-haiku-5-5"
    # Legacy, still available (ids already priced in config/other_models.json)
    CLAUDE_SONNET_5 = "claude-sonnet-5"
    CLAUDE_HAIKU_4_5 = "claude-haiku-4-5"
    # Legacy and available, but the page gives no id for them, so they are not used until verified:
    # Claude Fable 5, Opus 5, Opus 4.8, Opus 4.7, Opus 4.6, Opus 4.5, Sonnet 4.6
    # Not listed any more: the "-latest" ids of the 4.6, 4.5, 3.7 and 3.5 generations

class MistralModels(str, Enum):
    # Empty on purpose (T-02, decision 2 and 6): Mistral's pages name the current models (Large 4, Medium 3.5, Small 4,
    # Ministral 3, Codestral) but give no confirmed API id and no price, only documentation slugs. The provider route
    # and keys stay, so a verified id can be added here. Retired: mistral-large-2411 (2026-05-31), pixtral-large-2411.
    # Not confirmed: mistral-pi-01, codestral-mamba, pixtral-12b, mistral-small-latest
    pass

class GroqModels(str, Enum):
    # Production models of Groq's model list, 2026-10-27
    GPT_OSS_120B = "openai/gpt-oss-120b"
    GPT_OSS_20B = "openai/gpt-oss-20b"
    LLAMA3_3_70B = "llama-3.3-70b-versatile"
    LLAMA3_1_8B = "llama-3.1-8b-instant"
    # Preview only (evaluation, not production): qwen/qwen3.8-27b, minimaxai/minimax-m2.7
    # Not listed any more: llama4-70b-preview, llama4-8b-preview, llama-3.1-405b-reasoning, mixtral-8x7b-32768

class CohereModels(str, Enum):
    # Live Command models of Cohere's models page, 2026-10-27 (no price found for them)
    COMMAND_A_PLUS = "command-a-plus-05-2026"
    COMMAND_A = "command-a-03-2025"
    COMMAND_A_REASONING = "command-a-reasoning-08-2025"
    COMMAND_A_VISION = "command-a-vision-07-2025"
    COMMAND_R_08_2024 = "command-r-08-2024"
    COMMAND_R_PLUS_08_2024 = "command-r-plus-08-2024"
    # Deprecated 2025-09-15: command-r, command-r-plus (and their dated 03/04-2024 ids); command-r7 is command-r7b-12-2024

class OllamaModels(str, Enum):
    # Names of the Ollama library, 2026-10-27: none is marked deprecated; the page shows sizes, not full tags
    LLAMA4 = "llama4"
    LLAMA3_3 = "llama3.3"
    PHI_4 = "phi4"
    DEEPSEEK_V3 = "deepseek-v3"
    MISTRAL_NEMO = "mistral-nemo"


@dataclass(frozen=True)
class ModelIdList:
    """
    Namespace-style registry of supported LLM providers and models.
    Compatible with LangChain + LangSmith tracing.
    """
    OPENAI: type[OpenAIModels] = OpenAIModels
    GOOGLE: type[GoogleModels] = GoogleModels
    ANTHROPIC: type[AnthropicModels] = AnthropicModels
    MISTRAL: type[MistralModels] = MistralModels
    COHERE: type[CohereModels] = CohereModels
    GROQ: type[GroqModels] = GroqModels
    OLLAMA: type[OllamaModels] = OllamaModels


SupportedModel = Union[
    ModelIdList.OPENAI,
    ModelIdList.GOOGLE,
    ModelIdList.ANTHROPIC,
    ModelIdList.MISTRAL,
    ModelIdList.COHERE,
    ModelIdList.GROQ,
    ModelIdList.OLLAMA,
]
