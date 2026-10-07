from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class TokensUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

def create_tokens_usage(prompt_tokens: int, completion_tokens: int, total_tokens: int) -> TokensUsage:
    return TokensUsage(prompt_tokens, completion_tokens, total_tokens)
