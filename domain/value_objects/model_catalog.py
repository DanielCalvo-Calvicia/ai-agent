from dataclasses import dataclass
from enum import Enum
from typing import Union


class OpenAIModels(str, Enum):
    # GPT-5 Series (2026 Standard)
    GPT_5 = "gpt-5"
    GPT_5_TURBO = "gpt-5-turbo"
    GPT_5_MINI = "gpt-5-mini"
    # Legacy / Stable GPT-4 Series
    GPT_4_5 = "gpt-4.5"
    GPT_4O = "gpt-4o"
    GPT_4_TURBO = "gpt-4-turbo"
    O1 = "o1"
    O1_MINI = "o1-mini"
    O3_MINI = "o3-mini"

class GoogleModels(str, Enum):
    # Gemini 3 series (ids of Google's models page, September 2026; prices in config/gemini_models.json)
    GEMINI_3_8_FLASH = "gemini-3.8-flash"
    GEMINI_3_7_FLASH = "gemini-3.7-flash"
    GEMINI_3_6_FLASH = "gemini-3.6-flash"
    GEMINI_3_5_FLASH = "gemini-3.5-flash"
    GEMINI_3_5_FLASH_LITE = "gemini-3.5-flash-lite"
    GEMINI_3_1_FLASH_LITE = "gemini-3.1-flash-lite"
    GEMINI_3_1_PRO_PREVIEW = "gemini-3.1-pro-preview"
    GEMINI_3_FLASH_PREVIEW = "gemini-3-flash-preview"
    # Gemini 2.5 Series
    GEMINI_2_5_PRO = "gemini-2.5-pro"
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_2_5_FLASH_LITE = "gemini-2.5-flash-lite"
    # Stable 1.5
    GEMINI_1_5_PRO = "gemini-1.5-pro"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"

class AnthropicModels(str, Enum):
    # Claude 4.6 Series (Latest)
    CLAUDE_4_6_OPUS = "claude-4-6-opus-latest"
    CLAUDE_4_6_SONNET = "claude-4-6-sonnet-latest"
    # Claude 4.5 Series
    CLAUDE_4_5_SONNET = "claude-4-5-sonnet-latest"
    # Claude 3.7 & 3.5 (Stable/Legacy)
    CLAUDE_3_7_SONNET = "claude-3-7-sonnet-latest"
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet-latest"
    CLAUDE_3_5_HAIKU = "claude-3-5-haiku-latest"

class MistralModels(str, Enum):
    MISTRAL_LARGE_24 = "mistral-large-2411"
    MISTRAL_PI_01 = "mistral-pi-01" # Mistral's 2026 reasoning model
    MISTRAL_SMALL_LATEST = "mistral-small-latest"
    CODESTRAL_MAMBA = "codestral-mamba"
    PIXTRAL_12B = "pixtral-12b"

class GroqModels(str, Enum):
    # Open-weight OpenAI models on Groq (ids listed by the Groq API of this project's key, September 2026)
    GPT_OSS_120B = "openai/gpt-oss-120b"
    GPT_OSS_20B = "openai/gpt-oss-20b"
    # Llama 4 Series (Now available on Groq)
    LLAMA4_70B = "llama4-70b-preview"
    LLAMA4_8B = "llama4-8b-preview"
    # Llama 3.3 / 3.1
    LLAMA3_3_70B = "llama-3.3-70b-versatile"
    LLAMA3_1_405B = "llama-3.1-405b-reasoning"
    MIXTRAL_8X7B = "mixtral-8x7b-32768"

class CohereModels(str, Enum):
    COMMAND_R7 = "command-r7" # 2026 update
    COMMAND_R_PLUS = "command-r-plus"
    COMMAND_R = "command-r"

class OllamaModels(str, Enum):
    LLAMA4 = "llama4"
    LLAMA3_3 = "llama3.3"
    PHI_4 = "phi4"
    DEEPSEEK_V3 = "deepseek-v3"
    MISTRAL_NEMO = "mistral-nemo"

class GithubModels(str, Enum):
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4_1 = "gpt-4.1"
    GPT_4_1_MINI = "gpt-4.1-mini"
    GPT_4_1_NANO = "gpt-4.1-nano"
    GPT_4_5_PREVIEW = "gpt-4.5-preview"
    CHATGPT_4O_LATEST = "chatgpt-4o-latest"

    O1 = "o1"
    O1_MINI = "o1-mini"
    O3 = "o3"
    O3_MINI = "o3-mini"
    O3_PRO = "o3-pro"
    O4_MINI = "o4-mini"

    CLAUDE_3_5_SONNET_20240620 = "claude-3-5-sonnet-20240620"
    CLAUDE_3_5_SONNET_20241022 = "claude-3-5-sonnet-20241022"
    CLAUDE_3_5_HAIKU_20241022 = "claude-3-5-haiku-20241022"
    CLAUDE_3_7_SONNET_20250219 = "claude-3-7-sonnet-20250219"
    CLAUDE_SONNET_4_20250514 = "claude-sonnet-4-20250514"
    CLAUDE_SONNET_4_5_20250929 = "claude-sonnet-4-5-20250929"
    CLAUDE_HAIKU_4_5_20251001 = "claude-haiku-4-5-20251001"
    CLAUDE_OPUS_4_1_20250805 = "claude-opus-4-1-20250805"
    #CLAUDE_OPUS_4_5_20250929 = "claude-opus-4-5-20250929"

    GEMINI_1_5_PRO = "gemini-1.5-pro"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"
    GEMINI_1_5_FLASH_8B = "gemini-1.5-flash-8b"
    GEMINI_2_5_PRO = "gemini-2.5-pro"
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_2_5_FLASH_LITE = "gemini-2.5-flash-lite"
    GEMINI_2_5_PRO_GROUNDING_EXP = "gemini-2.5-pro-grounding-exp"
    
    GEMMA_3_27B_IT = "gemma-3-27b-it"
    GEMMA_3_12B_IT = "gemma-3-12b-it"
    GEMMA_3_4B_IT = "gemma-3-4b-it"

    LLAMA_3_3_70B_INSTRUCT = "llama-3.3-70b-instruct"
    LLAMA_3_2_90B_VISION_INSTRUCT = "llama-3.2-90b-vision-instruct"
    LLAMA_3_2_11B_VISION_INSTRUCT = "llama-3.3-11b-vision-instruct"
    LLAMA_3_1_405B_INSTRUCT = "llama-3.1-405b-instruct"
    LLAMA_3_1_70B_INSTRUCT = "llama-3.1-70b-instruct"
    LLAMA_3_1_8B_INSTRUCT = "llama-3.1-8b-instruct"

    MISTRAL_LARGE = "mistral-large"
    MISTRAL_MEDIUM = "mistral-medium"
    MISTRAL_SMALL = "mistral-small"
    MISTRAL_SMALL_2503 = "mistral-small-2503"
    MISTRAL_LARGE_2411 = "mistral-large-2411"
    OPEN_MISTRAL_NEMO = "open-mistral-nemo"

    CODESTRAL = "codestral"
    CODESTRAL_2501 = "codestral-2501"
    
    COMMAND_R_PLUS = "command-r+"
    COMMAND_R = "command-r"

    DEEPSEEK_CHAT = "deepseek-chat"
    DEEPSEEK_REASONER = "deepseek-reasoner"
    JAMBA_1_5_LARGE = "jamba-1.5-large"

    GROK_CODE_FAST_1 = "grok-code-fast-1"


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
    GITHUB: type[GithubModels] = GithubModels


SupportedModel = Union[
    ModelIdList.OPENAI,
    ModelIdList.GOOGLE,
    ModelIdList.ANTHROPIC,
    ModelIdList.MISTRAL,
    ModelIdList.COHERE,
    ModelIdList.GROQ,
    ModelIdList.OLLAMA,
    ModelIdList.GITHUB,
]

