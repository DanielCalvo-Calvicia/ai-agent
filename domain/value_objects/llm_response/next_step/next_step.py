

from dataclasses import dataclass, field
from typing import List, Optional

from .ready_to_execute import create_ready_to_execute, ReadyToExecute
from .status import create_status, Status
from .recommended_action import create_recommended_action, RecommendedAction
from .blocking_reason import create_blocking_reason, BlockingReason
from .requested_user_input import create_requested_user_input, RequestedUserInput
from .retry_action_id import create_retry_action_id, RetryActionId


@dataclass(frozen=True)
class NextStep:
    status: Status
    ready_to_execute: Optional[ReadyToExecute] = None
    recommended_action: Optional[RecommendedAction] = None
    blocking_reason: Optional[BlockingReason] = None
    requested_user_input: Optional[RequestedUserInput] = None
    # Not in the repr: the repr of a NextStep is pasted into some phase messages, and those must not change.
    retry_action_id: Optional[RetryActionId] = field(default=None, repr=False)

def create_next_step(
    ready_to_execute_value: bool,
    status_value: str,
    recommended_action_value: str,
    blocking_reason_value: str,
    requested_user_input_value: List[str],
    retry_action_id_value: Optional[str] = None
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
    requested_user_input: Optional[RequestedUserInput] = None
    if requested_user_input_value is not None and len(requested_user_input_value) > 0:
        requested_user_input = create_requested_user_input(requested_user_input_value)
    retry_action_id: Optional[RetryActionId] = None
    if retry_action_id_value is not None and retry_action_id_value != "":
        retry_action_id = create_retry_action_id(retry_action_id_value)

    next_step = NextStep(
        ready_to_execute=ready_to_execute,
        status=status,
        recommended_action=recommended_action,
        blocking_reason=blocking_reason,
        requested_user_input=requested_user_input,
        retry_action_id=retry_action_id
    )
    return next_step
