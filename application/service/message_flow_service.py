# -----------------------------------------------
#  PORTS
# -----------------------------------------------
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from application.inbound.ports.message_flow_ports import MessageInboundPort
from application.outbound.ports.llm_ports import LLMOutboundPort


# -----------------------------------------------
#  DOMAIN
# -----------------------------------------------
from domain.entities.payload import Payload
from domain.entities.response import Response

from domain.value_objects.intent.intent import Intent, create_intent
from domain.value_objects.max_tokens import MaxTokens, create_max_tokens
from domain.value_objects.message import Message, Role, create_message
from domain.value_objects.model import (
    SelectedModel,
    get_selected_model,
    GithubModels,
    GoogleModels,
)

from application.system_prompts.advanced import LoadSystemPrompt
from domain.value_objects.reasoning import ReasoningConfig, ReasoningEffort, create_reasoning_config
from domain.value_objects.response_format import ResponseFormat
from domain.value_objects.temperature import Temperature, create_temperature
from domain.value_objects.tool import ToolDefinition
from domain.value_objects.top_p import TopP

from domain.value_objects.task_category.complexity import get_schema as get_complexity_schema
from domain.value_objects.intent.intent import get_schema as get_intent_schema
from domain.value_objects.task_category.task_category import get_schema as get_task_category_schema
from domain.value_objects.mcp_routing.mcp_routing import get_schema as get_mcp_routing_schema
from domain.value_objects.next_step.next_step import get_schema as get_next_step_schema
from domain.value_objects.safety_and_validation.safety_and_validation import get_schema as get_safety_and_validation_schema
from domain.value_objects.user_goal.user_goal import create_user_goal, get_schema as get_user_goal_schema
from domain.entities.action import get_schema as get_actions_schema, Action
from domain.entities.tokens_usage import TokensUsage, create_tokens_usage


# -----------------------------------------------
#  DTOS
# -----------------------------------------------
from application.inbound.dto.message import TextRequestDTO, TextResponseDTO


# ===============================================
#  TRACKING
# ===============================================

PHASE_NAMES: Dict[int, str] = {
    1:  "triage_specialist",
    2:  "project_manager",
    3:  "safety_quality_gatekeeper",
    4:  "cognitive_worker",
    5:  "mcp_operator",
    6:  "data_engineer",
    7:  "draft_writer",
    8:  "editor_in_chief",
    99: "user_clarification",
}


@dataclass
class TokenCount:
    """Accumulated token counts plus a request counter."""
    prompt: int = 0
    completion: int = 0
    total: int = 0
    requests: int = 0

    def add(self, prompt: int, completion: int, total: int) -> None:
        self.prompt += prompt
        self.completion += completion
        self.total += total
        self.requests += 1

    def to_dict(self) -> Dict[str, int]:
        return {
            "prompt": self.prompt,
            "completion": self.completion,
            "total": self.total,
            "requests": self.requests,
        }


@dataclass
class RequestRecord:
    """Immutable snapshot of a single LLM call."""
    request_id: str
    phase_id: int
    phase_name: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    action_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id":       self.request_id,
            "phase_id":         self.phase_id,
            "phase_name":       self.phase_name,
            "model":            self.model,
            "prompt_tokens":    self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens":     self.total_tokens,
            "action_id":        self.action_id,
        }


class SessionMetrics:
    """
    Full observability for one agent session.

    Attributes
    ----------
    request_log : List[RequestRecord]
        Ordered log of every LLM call made during the session.

    by_phase : Dict[phase_name, Dict[model, TokenCount]]
        Token aggregation grouped first by phase then by model.
        e.g. metrics.by_phase["cognitive_worker"]["gpt-4.1"].total

    by_model : Dict[model, TokenCount]
        Cross-phase token aggregation per model.
        e.g. metrics.by_model["gpt-4.1"].total

    totals : TokenCount
        Grand total across the entire session.
    """

    def __init__(self) -> None:
        self.request_log: List[RequestRecord] = []
        self.by_phase:    Dict[str, Dict[str, TokenCount]] = {}
        self.by_model:    Dict[str, TokenCount] = {}
        self.totals:      TokenCount = TokenCount()

    # ------------------------------------------

    def record(
        self,
        phase_id:   int,
        model:      str,
        prompt:     int,
        completion: int,
        total:      int,
        action_id:  Optional[str] = None,
    ) -> str:
        """
        Record one LLM call. Returns the generated request_id.
        Updates by_phase, by_model, and totals in one pass.
        """
        phase_name = PHASE_NAMES.get(phase_id, f"phase_{phase_id}")
        request_id = uuid.uuid4().hex[:12]

        # ---- request log -------------------------------------------
        self.request_log.append(RequestRecord(
            request_id=request_id,
            phase_id=phase_id,
            phase_name=phase_name,
            model=model,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            action_id=action_id,
        ))

        # ---- by_phase[phase_name][model] ---------------------------
        phase_bucket = self.by_phase.setdefault(phase_name, {})
        phase_bucket.setdefault(model, TokenCount()).add(prompt, completion, total)

        # ---- by_model[model] ---------------------------------------
        self.by_model.setdefault(model, TokenCount()).add(prompt, completion, total)

        # ---- session totals ----------------------------------------
        self.totals.add(prompt, completion, total)

        return request_id

    # ------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Returns a fully serialisable summary dict for logging or inspection."""
        return {
            "total_requests":           self.totals.requests,
            "total_prompt_tokens":      self.totals.prompt,
            "total_completion_tokens":  self.totals.completion,
            "total_tokens":             self.totals.total,
            "by_phase": {
                phase: {
                    model: tc.to_dict()
                    for model, tc in models.items()
                }
                for phase, models in self.by_phase.items()
            },
            "by_model": {
                model: tc.to_dict()
                for model, tc in self.by_model.items()
            },
            "request_log": [
                r.to_dict() for r in self.request_log
            ],
        }



# ===============================================
#  SERVICE
# ===============================================

class MessageFlowService(MessageInboundPort):
    outbound_port: LLMOutboundPort
    mcp_list: list
    metrics: SessionMetrics
    flow_response: Response

    def __init__(self, outbound_port: LLMOutboundPort, mcp_list: Optional[list] = None):
        self.outbound_port = outbound_port
        self.metrics = SessionMetrics()
        self.mcp_list = mcp_list if mcp_list is not None else []

    # -----------------------------------------------
    #  INBOUND
    # -----------------------------------------------

    def text(self, request: TextRequestDTO) -> TextResponseDTO:
        result = self.main_flow(request.content)
        return TextResponseDTO(
            content=result,
            is_final=True,
            success=True
        )

    # -----------------------------------------------
    #  ORCHESTRATION
    # -----------------------------------------------

    def main_flow(self, message: str) -> str:

        # Phase 1 - Triage Specialist
        # Classifies intent, extracts user goal and task category.
        self.flow_response = self.phase1_triage_specialist(message)

        # Phase 2 - Project Manager
        # Decomposes the goal into actions and identifies required inputs per action.
        response_phase2 = self.phase2_project_manager()
        self.flow_response.actions = response_phase2.actions
        self.flow_response.next_step = response_phase2.next_step
        if self._requires_user_input():
            return self._synthesize_user_clarification()

        # Phase 3 - Safety & Quality Gatekeeper
        # Validates actions for safety and decides if user confirmation is needed.
        response_phase3 = self.phase3_safety_quality_gatekeeper()
        self.flow_response.safety_and_validation = response_phase3.safety_and_validation
        self.flow_response.next_step = response_phase3.next_step
        if self._requires_user_input():
            return self._synthesize_user_clarification()

        # Phase 4 - Cognitive Worker
        # Each non-MCP action is executed in its own LLM request.
        self.phase4_cognitive_worker()

        # Phase 5 - MCP Operator
        # Each MCP tool-call action is executed in its own LLM request.
        self.phase5_mcp_operator()

        # Phase 6 - Data Engineer
        # Each action output is normalized in its own LLM request.
        self.phase6_data_engineer()

        # Phase 7 - Draft Writer
        # Synthesizes all action outputs into a first draft of the user response.
        response_phase7 = self.phase7_draft_writer()
        if response_phase7.user_goal:
            self.flow_response.user_goal = response_phase7.user_goal

        # Phase 8 - Editor in Chief
        # Polishes the draft and produces the final response for the user.
        response_phase8 = self.phase8_editor_in_chief()
        if response_phase8.user_goal:
            self.flow_response.user_goal = response_phase8.user_goal
        if response_phase8.next_step:
            self.flow_response.next_step = response_phase8.next_step

        if (
            self.flow_response.user_goal
            and self.flow_response.user_goal.expected_outcome
        ):
            return self.flow_response.user_goal.expected_outcome.get_value()

        return ""

    # -----------------------------------------------
    #  FLOW CONTROL HELPERS
    # -----------------------------------------------

    def _requires_user_input(self) -> bool:
        """
        Returns True when next_step signals the flow must pause for the user.
        Per the generic prompt, next_step is the authoritative control flow object.
        Triggers on status: awaiting_user_input or awaiting_confirmation.
        """
        if not self.flow_response or not self.flow_response.next_step:
            return False

        status = self.flow_response.next_step.status
        if status and status.get_value() in ("awaiting_user_input", "awaiting_confirmation"):
            return True

        return False

    def _synthesize_user_clarification(self) -> str:
        """
        Collects required inputs from next_step.request_user_input and
        actions[].required_inputs, then asks the LLM to produce a clear,
        user-facing clarification message.
        """
        required_inputs: List[str] = []

        if (
            self.flow_response.next_step
            and self.flow_response.next_step.request_user_input
            and self.flow_response.next_step.request_user_input.get_length() > 0
        ):
            required_inputs.extend(self.flow_response.next_step.request_user_input.get_value())

        if self.flow_response.actions:
            for action in self.flow_response.actions:
                if action.required_inputs and action.required_inputs.get_length() > 0:
                    required_inputs.extend(action.required_inputs.get_value())

        # Fallback to blocking_reason or recommended_action if nothing was collected
        if not required_inputs and self.flow_response.next_step:
            if self.flow_response.next_step.blocking_reason:
                required_inputs = [self.flow_response.next_step.blocking_reason.get_value()]
            elif self.flow_response.next_step.recommended_action:
                required_inputs = [self.flow_response.next_step.recommended_action.get_value()]

        if not required_inputs:
            return "Additional information is required to proceed. Please provide more details."

        intent = create_intent(
            primary="clarification_request",
            secondary=[],
            confidence=1.0
        )
        model: SelectedModel = get_selected_model(GithubModels.GPT_4_1)

        system_prompt_str = (
            "You are communicating directly with an end user. "
            "Write a clear, friendly message asking for the information listed below. "
            "Be concise. Do not expose internal system details."
        )
        system_prompt: Optional[Message] = create_message(Role.SYSTEM, system_prompt_str)

        inputs_text = "\n".join(f"- {item}" for item in required_inputs)
        user_message_str = f"The following information is required from the user:\n{inputs_text}"
        message: Message = create_message(Role.USER, user_message_str)

        reasoning: Optional[ReasoningConfig] = None
        temperature: Temperature = create_temperature(0.7)
        top_p: Optional[TopP] = None
        seed: Optional[int] = None
        max_tokens: MaxTokens = create_max_tokens(2000)
        response_format: Optional[ResponseFormat] = None
        tools: list[ToolDefinition] = []
        metadata: Dict[str, Any] = {}

        payload: Payload = Payload(
            intent=intent,
            model=model,
            system_prompt=system_prompt,
            message=message,
            reasoning=reasoning,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
            max_tokens=max_tokens,
            response_format=response_format,
            tools=tools,
            metadata=metadata
        )

        response = self.outbound_port.ask(payload)

        if not isinstance(response, Response):
            raise Exception("Invalid response type")

        self._track_response(response, 99, model)

        return response.text or ""

    def _track_response(
        self,
        response:  Response,
        phase_id:  int,
        model:     SelectedModel,
        action_id: Optional[str] = None,
    ) -> None:
        """
        Records one LLM call into self.metrics.
        Silently skips if the response carries no token usage data.
        """
        if response.tokens_usage:
            self.metrics.record(
                phase_id=phase_id,
                model=model.id,
                prompt=response.tokens_usage.prompt_tokens,
                completion=response.tokens_usage.completion_tokens,
                total=response.tokens_usage.total_tokens,
                action_id=action_id,
            )

    def _build_system_prompt(self, phase: int) -> Optional[Message]:
        """
        Combines the generic invariants prompt (phase 0) with the
        phase-specific prompt and returns a SYSTEM message.
        """
        universal_prompt = LoadSystemPrompt(phase=0)
        phase_prompt = LoadSystemPrompt(phase=phase)

        system_prompt_str = ""
        if universal_prompt:
            system_prompt_str += universal_prompt + "\n\n"
        if phase_prompt:
            system_prompt_str += phase_prompt

        return create_message(Role.SYSTEM, system_prompt_str)

    def _request_single_action(
        self,
        action: Action,
        phase: int,
        user_message_extra: Dict[str, Any],
        tools: Optional[list] = None,
        action_id: Optional[str] = None,
    ) -> Response:
        """
        Makes a single LLM call to process one action.
        Used by phases 4, 5, and 6 to reduce per-request complexity.
        The caller reads response.actions[0] for the processed result.
        Automatically records the call into self.metrics keyed by action_id.
        """
        intent = create_intent(
            primary="decision_support",
            secondary=[],
            confidence=0.9
        )
        model: SelectedModel = get_selected_model(GithubModels.GPT_4_1)
        system_prompt: Optional[Message] = self._build_system_prompt(phase=phase)

        user_message = {"action": action, **user_message_extra}
        message: Message = create_message(Role.USER, user_message.__str__())

        reasoning: Optional[ReasoningConfig] = None
        temperature: Temperature = create_temperature(1.0)
        top_p: Optional[TopP] = None
        seed: Optional[int] = None
        max_tokens: MaxTokens = create_max_tokens(10000)

        response_format_action: Dict[str, Any] = get_actions_schema()

        response_format: Optional[ResponseFormat] = ResponseFormat(
            name=f"phase{phase}_single_action_response_format",
            schema={
                "type": "object",
                "required": ["actions"],
                "properties": {
                    "actions": response_format_action,
                }
            }
        )

        payload: Payload = Payload(
            intent=intent,
            model=model,
            system_prompt=system_prompt,
            message=message,
            reasoning=reasoning,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
            max_tokens=max_tokens,
            response_format=response_format,
            tools=tools if tools is not None else [],
            metadata={}
        )

        response = self.outbound_port.ask(payload)

        if not isinstance(response, Response):
            raise Exception("Invalid response type")

        self._track_response(response, phase, model, action_id=action_id)

        return response

    def _get_subactions(self, action: Action) -> List[Action]:
        """
        Returns the subactions of an action as a flat list.
        Handles both dict and list storage since the Python model uses dict
        but the JSON schema defines an array.
        """
        if not action.subtasks:
            return []
        if isinstance(action.subtasks, dict):
            return list(action.subtasks.values())
        if isinstance(action.subtasks, list):
            return list(action.subtasks)
        return []

    def _process_action_recursive(
        self,
        action: Action,
        phase: int,
        completed_outputs: Dict[str, str],
        extra_context: Optional[Dict[str, Any]] = None,
        tools: Optional[list] = None,
        skip_type: Optional[str] = None,
        only_type: Optional[str] = None,
    ) -> Optional[str]:
        """
        Depth-first recursive action executor:
        1. Applies type filters (skip_type / only_type) — returns None if this
           action does not match the current phase's responsibility.
        2. Recursively processes all subactions first, propagating the same
           filters so each nesting level stays in-phase.
        3. Resolves dependency outputs from the shared completed_outputs map.
        4. Makes a single focused LLM call for this action with full context
           (subaction outputs + dependency outputs).
        5. Updates the action in-place and returns the output string.
        """
        action_type_val = action.action_type.get_value() if action.action_type else None

        if skip_type and action_type_val == skip_type:
            return None
        if only_type and action_type_val != only_type:
            return None

        # Step 1 — recurse into subactions before executing the parent
        subactions = self._get_subactions(action)
        subaction_outputs: Dict[str, str] = {}
        for subaction in subactions:
            sub_output = self._process_action_recursive(
                action=subaction,
                phase=phase,
                completed_outputs=completed_outputs,
                extra_context=extra_context,
                tools=tools,
                skip_type=skip_type,
                only_type=only_type,
            )
            if sub_output:
                sub_id = subaction.id.get_value()
                subaction_outputs[sub_id] = sub_output
                completed_outputs[sub_id] = sub_output

        # Step 2 — resolve declared dependencies from the completed map
        dependency_outputs: Dict[str, str] = {}
        if action.dependencies:
            for dep_id in action.dependencies.get_value():
                if dep_id in completed_outputs:
                    dependency_outputs[dep_id] = completed_outputs[dep_id]

        # Step 3 — build context and make the LLM call for this single action
        user_message_extra: Dict[str, Any] = dict(extra_context or {})
        user_message_extra["dependency_outputs"] = dependency_outputs
        if subaction_outputs:
            user_message_extra["subaction_outputs"] = subaction_outputs

        response = self._request_single_action(
            action=action,
            phase=phase,
            user_message_extra=user_message_extra,
            tools=tools,
            action_id=action.id.get_value(),
        )

        if response.actions:
            executed = response.actions[0]
            if executed.output:
                output_val = executed.output.get_value()
                try:
                    action.mark_success(output_val)
                except Exception:
                    action.output = executed.output
                return output_val

        return None

    def _mark_mcp_actions_blocked_recursive(self, actions: List[Action]) -> None:
        """
        Recursively marks every MCP tool-call action in the tree as failed
        with a confirmation-blocked message. Subactions are visited first.
        """
        for action in actions:
            subactions = self._get_subactions(action)
            if subactions:
                self._mark_mcp_actions_blocked_recursive(subactions)
            if action.action_type and action.action_type.get_value() == "mcp_tool_call":
                action.mark_failed("Execution blocked: requires user confirmation before running MCP tools.")

    def _normalize_action_recursive(self, action: Action) -> None:
        """
        Recursively normalizes action outputs depth-first:
        subaction outputs are cleaned before the parent's output.
        Skips actions that have no output yet.
        """
        for subaction in self._get_subactions(action):
            self._normalize_action_recursive(subaction)

        if not action.output:
            return

        response = self._request_single_action(
            action=action,
            phase=6,
            user_message_extra={},
            action_id=action.id.get_value(),
        )

        if response.actions:
            normalized = response.actions[0]
            if normalized.output:
                normalized_val = normalized.output.get_value()
                try:
                    action.mark_success(normalized_val)
                except Exception:
                    action.output = normalized.output

    # -----------------------------------------------
    #  PHASE 1 - TRIAGE SPECIALIST
    # -----------------------------------------------

    def phase1_triage_specialist(self, init_message: str) -> Response:
        intent: Intent = create_intent(
            primary="clarification_request",
            secondary=["information_request"],
            confidence=1.0
        )
        model: SelectedModel = get_selected_model(GithubModels.GPT_4_1_MINI)
        system_prompt: Optional[Message] = self._build_system_prompt(phase=1)

        message: Message = create_message(Role.USER, init_message)

        reasoning: Optional[ReasoningConfig] = None
        temperature: Temperature = create_temperature(1.0)
        top_p: Optional[TopP] = None
        seed: Optional[int] = None
        max_tokens: MaxTokens = create_max_tokens(10000)

        response_format_intent: Dict[str, Any] = get_intent_schema()
        response_format_user_goal: Dict[str, Any] = get_user_goal_schema()
        response_format_task_category: Dict[str, Any] = get_task_category_schema()
        response_format_next_step: Dict[str, Any] = get_next_step_schema()

        response_format: Optional[ResponseFormat] = ResponseFormat(
            name="triage_specialist_phase1_response_format",
            schema={
                "type": "object",
                "required": [
                    "intent",
                    "user_goal",
                    "task_category",
                    "next_step",
                ],
                "properties": {
                    "intent": response_format_intent["intent"],
                    "user_goal": response_format_user_goal["user_goal"],
                    "task_category": response_format_task_category["task_category"],
                    "next_step": response_format_next_step["next_step"],
                }
            }
        )

        tools: list[ToolDefinition] = []
        metadata: Dict[str, Any] = {}

        payload: Payload = Payload(
            intent=intent,
            model=model,
            system_prompt=system_prompt,
            message=message,
            reasoning=reasoning,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
            max_tokens=max_tokens,
            response_format=response_format,
            tools=tools,
            metadata=metadata
        )

        response = self.outbound_port.ask(payload)

        if not isinstance(response, Response):
            raise Exception("Invalid response type")

        self._track_response(response, 1, model)

        return response

    # -----------------------------------------------
    #  PHASE 2 - PROJECT MANAGER
    # -----------------------------------------------

    def phase2_project_manager(self) -> Response:
        intent = create_intent(
            primary="decision_support",
            secondary=["information_request"],
            confidence=0.9
        )
        model: SelectedModel = get_selected_model(GithubModels.GPT_4_1)
        system_prompt: Optional[Message] = self._build_system_prompt(phase=2)

        user_message = {
            "user_goal": self.flow_response.user_goal,
            "task_category": self.flow_response.task_category,
            "available_mcp_servers": self.mcp_list,
        }
        message: Message = create_message(Role.USER, user_message.__str__())

        reasoning: Optional[ReasoningConfig] = None
        temperature: Temperature = create_temperature(1.0)
        top_p: Optional[TopP] = None
        seed: Optional[int] = None
        max_tokens: MaxTokens = create_max_tokens(10000)

        response_format_action: Dict[str, Any] = get_actions_schema()
        response_format_next_step: Dict[str, Any] = get_next_step_schema()
        response_format_task_category_complexity: Dict[str, Any] = get_complexity_schema()

        response_format: Optional[ResponseFormat] = ResponseFormat(
            name="project_manager_phase2_response_format",
            schema={
                "type": "object",
                "required": [
                    "actions",
                    "next_step",
                    "task_category_complexity",
                ],
                "properties": {
                    "actions": response_format_action,
                    "next_step": response_format_next_step["next_step"],
                    "task_category_complexity": response_format_task_category_complexity["complexity"],
                }
            }
        )

        tools: list[ToolDefinition] = []
        metadata: Dict[str, Any] = {}

        payload: Payload = Payload(
            intent=intent,
            model=model,
            system_prompt=system_prompt,
            message=message,
            reasoning=reasoning,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
            max_tokens=max_tokens,
            response_format=response_format,
            tools=tools,
            metadata=metadata
        )

        response = self.outbound_port.ask(payload)

        if not isinstance(response, Response):
            raise Exception("Invalid response type")

        self._track_response(response, 2, model)

        return response

    # -----------------------------------------------
    #  PHASE 3 - SAFETY & QUALITY GATEKEEPER
    # -----------------------------------------------

    def phase3_safety_quality_gatekeeper(self) -> Response:
        intent = create_intent(
            primary="decision_support",
            secondary=["information_request"],
            confidence=0.9
        )
        model: SelectedModel = get_selected_model(GithubModels.GPT_4_1)
        system_prompt: Optional[Message] = self._build_system_prompt(phase=3)

        user_message = {
            "actions": self.flow_response.actions,
            "next_step": self.flow_response.next_step,
        }
        message: Message = create_message(Role.USER, user_message.__str__())

        reasoning: Optional[ReasoningConfig] = None
        temperature: Temperature = create_temperature(1.0)
        top_p: Optional[TopP] = None
        seed: Optional[int] = None
        max_tokens: MaxTokens = create_max_tokens(10000)

        response_format_safety: Dict[str, Any] = get_safety_and_validation_schema()
        response_format_next_step: Dict[str, Any] = get_next_step_schema()

        response_format: Optional[ResponseFormat] = ResponseFormat(
            name="safety_quality_gatekeeper_phase3_response_format",
            schema={
                "type": "object",
                "required": [
                    "safety_and_validation",
                    "next_step",
                ],
                "properties": {
                    "safety_and_validation": response_format_safety["safety_and_validation"],
                    "next_step": response_format_next_step["next_step"],
                }
            }
        )

        tools: list[ToolDefinition] = []
        metadata: Dict[str, Any] = {}

        payload: Payload = Payload(
            intent=intent,
            model=model,
            system_prompt=system_prompt,
            message=message,
            reasoning=reasoning,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
            max_tokens=max_tokens,
            response_format=response_format,
            tools=tools,
            metadata=metadata
        )

        response = self.outbound_port.ask(payload)

        if not isinstance(response, Response):
            raise Exception("Invalid response type")

        self._track_response(response, 3, model)

        return response

    # -----------------------------------------------
    #  PHASE 4 - COGNITIVE WORKER
    # -----------------------------------------------

    def phase4_cognitive_worker(self) -> None:
        """
        Executes each non-MCP action by delegating to _process_action_recursive.
        Each action (and every level of its subactions) is processed in its own
        LLM request, depth-first, so the parent always has subaction outputs available.
        MCP actions at any nesting level are skipped (handled by phase 5).
        """
        if not self.flow_response.actions:
            return

        completed_outputs: Dict[str, str] = {}

        for action in self.flow_response.actions:
            output = self._process_action_recursive(
                action=action,
                phase=4,
                completed_outputs=completed_outputs,
                extra_context={"user_goal": self.flow_response.user_goal},
                skip_type="mcp_tool_call",
            )
            if output:
                completed_outputs[action.id.get_value()] = output

    # -----------------------------------------------
    #  PHASE 5 - MCP OPERATOR
    # -----------------------------------------------

    def phase5_mcp_operator(self) -> None:
        """
        Executes each MCP tool-call action by delegating to _process_action_recursive.
        If safety requires confirmation, all MCP actions in the entire tree are
        marked as blocked immediately (via _mark_mcp_actions_blocked_recursive).
        Otherwise, each MCP action and its MCP subactions run depth-first,
        one LLM call each.
        """
        if not self.flow_response.actions:
            return

        requires_confirmation = bool(
            self.flow_response.safety_and_validation
            and self.flow_response.safety_and_validation.requires_confirmation
            and self.flow_response.safety_and_validation.requires_confirmation.get_value()
        )

        if requires_confirmation:
            self._mark_mcp_actions_blocked_recursive(self.flow_response.actions)
            return

        completed_outputs: Dict[str, str] = {}

        for action in self.flow_response.actions:
            output = self._process_action_recursive(
                action=action,
                phase=5,
                completed_outputs=completed_outputs,
                extra_context={
                    "available_mcp_servers": self.mcp_list,
                    "safety_and_validation": self.flow_response.safety_and_validation,
                },
                tools=self.mcp_list,
                only_type="mcp_tool_call",
            )
            if output:
                completed_outputs[action.id.get_value()] = output

    # -----------------------------------------------
    #  PHASE 6 - DATA ENGINEER
    # -----------------------------------------------

    def phase6_data_engineer(self) -> None:
        """
        Normalizes each action's raw output by delegating to _normalize_action_recursive.
        Each action in the tree is normalized in its own LLM request, depth-first,
        so subaction outputs are clean before the parent is processed.
        """
        if not self.flow_response.actions:
            return

        for action in self.flow_response.actions:
            self._normalize_action_recursive(action)

    # -----------------------------------------------
    #  PHASE 7 - DRAFT WRITER
    # -----------------------------------------------

    def phase7_draft_writer(self) -> Response:
        intent = create_intent(
            primary="decision_support",
            secondary=["information_request"],
            confidence=0.9
        )
        model: SelectedModel = get_selected_model(GithubModels.GPT_4_1)
        system_prompt: Optional[Message] = self._build_system_prompt(phase=7)

        user_message = {
            "user_goal": self.flow_response.user_goal,
            "task_category": self.flow_response.task_category,
            "actions": self.flow_response.actions,
            "constraints": self.flow_response.constraints,
        }
        message: Message = create_message(Role.USER, user_message.__str__())

        reasoning: Optional[ReasoningConfig] = None
        temperature: Temperature = create_temperature(1.0)
        top_p: Optional[TopP] = None
        seed: Optional[int] = None
        max_tokens: MaxTokens = create_max_tokens(10000)

        response_format_user_goal: Dict[str, Any] = get_user_goal_schema()

        response_format: Optional[ResponseFormat] = ResponseFormat(
            name="draft_writer_phase7_response_format",
            schema={
                "type": "object",
                "required": [
                    "user_goal",
                ],
                "properties": {
                    "user_goal": response_format_user_goal["user_goal"],
                }
            }
        )

        tools: list[ToolDefinition] = []
        metadata: Dict[str, Any] = {}

        payload: Payload = Payload(
            intent=intent,
            model=model,
            system_prompt=system_prompt,
            message=message,
            reasoning=reasoning,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
            max_tokens=max_tokens,
            response_format=response_format,
            tools=tools,
            metadata=metadata
        )

        response = self.outbound_port.ask(payload)

        if not isinstance(response, Response):
            raise Exception("Invalid response type")

        self._track_response(response, 7, model)

        return response

    # -----------------------------------------------
    #  PHASE 8 - EDITOR IN CHIEF
    # -----------------------------------------------

    def phase8_editor_in_chief(self) -> Response:
        intent = create_intent(
            primary="decision_support",
            secondary=["information_request"],
            confidence=0.9
        )
        model: SelectedModel = get_selected_model(GithubModels.GPT_4_1)
        system_prompt: Optional[Message] = self._build_system_prompt(phase=8)

        user_message = {
            "user_goal": self.flow_response.user_goal,
            "constraints": self.flow_response.constraints,
            "next_step": self.flow_response.next_step,
        }
        message: Message = create_message(Role.USER, user_message.__str__())

        reasoning: Optional[ReasoningConfig] = None
        temperature: Temperature = create_temperature(1.0)
        top_p: Optional[TopP] = None
        seed: Optional[int] = None
        max_tokens: MaxTokens = create_max_tokens(10000)

        response_format_user_goal: Dict[str, Any] = get_user_goal_schema()
        response_format_next_step: Dict[str, Any] = get_next_step_schema()

        response_format: Optional[ResponseFormat] = ResponseFormat(
            name="editor_in_chief_phase8_response_format",
            schema={
                "type": "object",
                "required": [
                    "user_goal",
                    "next_step",
                ],
                "properties": {
                    "user_goal": response_format_user_goal["user_goal"],
                    "next_step": response_format_next_step["next_step"],
                }
            }
        )

        tools: list[ToolDefinition] = []
        metadata: Dict[str, Any] = {}

        payload: Payload = Payload(
            intent=intent,
            model=model,
            system_prompt=system_prompt,
            message=message,
            reasoning=reasoning,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
            max_tokens=max_tokens,
            response_format=response_format,
            tools=tools,
            metadata=metadata
        )

        response = self.outbound_port.ask(payload)

        if not isinstance(response, Response):
            raise Exception("Invalid response type")

        self._track_response(response, 8, model)

        return response
