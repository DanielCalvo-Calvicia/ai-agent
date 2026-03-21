from dataclasses import dataclass, field
import json
from typing import Dict, List, Optional

from domain.entities.action import Action

@dataclass
class FlowActions:
    primary: Action
    secondary: Optional[Dict[str, FlowActions]] = None



@dataclass
class FlowResponse:
    initial_prompt: Optional[str] = None
    main_user_goal: Optional[str] = None
    actions: Optional[Dict[str, FlowActions]] = None