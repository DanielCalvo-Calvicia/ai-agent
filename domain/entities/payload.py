from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

from domain.value_objects.intent.intent import Intent
from domain.value_objects.model import SelectedModel, SupportedModel
from domain.value_objects.message import Message, Role
from domain.value_objects.reasoning import ReasoningConfig, ReasoningEffort
from domain.value_objects.temperature import Temperature
from domain.value_objects.max_tokens import MaxTokens
from domain.value_objects.response_format import ResponseFormat
from domain.value_objects.tool import ToolDefinition
from domain.value_objects.top_p import TopP

@dataclass
class Payload:
    intent: Intent
    model: SelectedModel
    system_prompt: Optional[Message]
    message: Message
    reasoning: Optional[ReasoningConfig] = None
    temperature: Temperature = field(default_factory=lambda: Temperature(1.0))
    top_p: Optional[TopP]= field(default_factory=lambda: TopP(1.0))
    seed: Optional[int] = None
    max_tokens: MaxTokens = field(default_factory=lambda: MaxTokens(1024))
    response_format: Optional[ResponseFormat] = None
    tools: list[ToolDefinition]= field(default_factory=list)
    metadata: Dict[str, Any]= field(default_factory=dict)

    def __post_init__(self):
        """Cross-field validation (e.g., specific models requiring specific formats)."""
        if self.reasoning and not self.model.is_openai():
            # Example: Only certain providers support explicit reasoning effort
            pass

    def to_dict(self) -> Dict[str, Any]:
        """
        Serializes the entire entity into a standard dictionary 
        suitable for JSON payloads or LangChain inputs.
        """
        payload_dict = {
            "model": self.model.id,
            "messages": [{"role": self.message.role.value, "content": self.message.content}],
            "temperature": self.temperature.value,
            "max_tokens": self.max_tokens.value,
        }
        
        if self.tools:
            payload_dict["tools"] = [t.to_openai_dict() for t in self.tools]
            
        if self.response_format:
            payload_dict["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": self.response_format.name,
                    "schema": self.response_format.schema
                }
            }
            
        return payload_dict