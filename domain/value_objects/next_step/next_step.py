

from dataclasses import dataclass, field
import json
from typing import List, Optional

from .ready_to_execute import create_ready_to_execute, ReadyToExecute
from .status import create_status, Status
from .recommended_action import create_recommended_action, RecommendedAction
from .blocking_reason import create_blocking_reason, BlockingReason
from .request_user_input import create_request_user_input, RequestUserInput

schema_path = "schema/response/next_steps/next_step.schema.json"
schema_base_path = "schema/response/next_steps/next_step.base.schema.json"

@dataclass(frozen=True)
class NextStep:
    status: Status
    ready_to_execute: Optional[ReadyToExecute] = None
    recommended_action: Optional[RecommendedAction] = None
    blocking_reason: Optional[BlockingReason] = None
    request_user_input: Optional[RequestUserInput] = None

def create_next_step(
    ready_to_execute_value: bool,
    status_value: str,
    recommended_action_value: str,
    blocking_reason_value: str,
    request_user_input_value: List[str]
):
    ready_to_execute: Optional[ReadyToExecute] = None
    if ready_to_execute_value is not None: 
        ready_to_execute = create_ready_to_execute(ready_to_execute_value)
    status = create_status(status_value)
    recommended_action: Optional[RecommendedAction] = None
    if recommended_action_value is not None and recommended_action_value != "":
        recommended_action = create_recommended_action(recommended_action_value)
    blocking_reason: Optional[BlockingReason] = None
    if blocking_reason_value is not None and blocking_reason_value != "":
        blocking_reason = create_blocking_reason(blocking_reason_value)
    request_user_input: Optional[RequestUserInput] = None
    if request_user_input_value is not None and len(request_user_input_value) > 0:
        request_user_input = create_request_user_input(request_user_input_value)

    next_step = NextStep(
        ready_to_execute=ready_to_execute,
        status=status,
        recommended_action=recommended_action,
        blocking_reason=blocking_reason,
        request_user_input=request_user_input
    )
    return next_step

def get_schema():
    # Load the schema from your local file
    with open(schema_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic

def get_base_schema():
    # Load the base schema from your local file
    with open(schema_base_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic