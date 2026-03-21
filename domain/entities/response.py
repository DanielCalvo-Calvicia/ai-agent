from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from domain.value_objects.intent.intent import Intent, create_intent
from domain.value_objects.user_goal.user_goal import UserGoal, create_user_goal
from domain.value_objects.mcp_routing.mcp_routing import MCPRouting, create_mcp_routing
from domain.value_objects.task_category.task_category import TaskCategory, create_task_category
from domain.entities.action import Action, create_action
from domain.value_objects.constraints.constraints import Constraints, create_constraints
from domain.value_objects.safety_and_validation.safety_and_validation import SafetyAndValidation, create_safety_and_validation
from domain.value_objects.next_step.next_step import NextStep, create_next_step
from domain.value_objects.missing_information.missing_information import MissingInformation, create_missing_information
from domain.entities.tokens_usage import TokensUsage, create_tokens_usage

# -----------------------------
# Type Errors
# -----------------------------
ErrResponseIntentInvalidType = TypeError("intent must be IntentResponse")
ErrResponseUserGoalInvalidType = TypeError("user_goal must be UserGoalResponse")
ErrResponseMcpRoutingInvalidType = TypeError("mcp_routing must be MCPRoutingResponse")
ErrResponseTaskCategoryInvalidType = TypeError("task_category must be TaskCategoryResponse")
ErrResponseActionInvalidType = TypeError("action must be ActionResponse")
ErrResponseConstraintsInvalidType = TypeError("constraints must be ConstraintsResponse")
ErrResponseSafetyInvalidType = TypeError("safety_and_validation must be SafetyAndValidationResponse")
ErrResponseNextStepInvalidType = TypeError("next_step must be NextStepResponse")
ErrResponseMissingInformationInvalidType = TypeError("missing_information must be a list")

# -----------------------------
# Validation Errors
# -----------------------------
ErrResponseMissingInformationInvalidItem = ValueError("missing_information must contain non-empty strings")
ErrResponseMissingInformationEmptyValue = ValueError("Missing information must be non-empty string.")


@dataclass
class Response:
    intent: Optional[Intent]
    user_goal: Optional[UserGoal]
    mcp_routing: Optional[MCPRouting]
    task_category: Optional[TaskCategory]
    actions: Optional[List[Action]]
    missing_information: Optional[MissingInformation] = None
    constraints: Optional[Constraints] = None
    safety_and_validation: Optional[SafetyAndValidation] = None
    next_step: Optional[NextStep] = None
    tokens_usage: Optional[TokensUsage] = None

    # -----------------------------
    # Initialization
    # -----------------------------
    def __post_init__(self):
        #self.validate()
        pass
    '''
    # -----------------------------
    # Validation
    # -----------------------------
    def validate(self):
        self._validate_intent()
        self._validate_user_goal()
        self._validate_mcp_routing()
        self._validate_task_category()
        self._validate_actions()
        self._validate_constraints()
        self._validate_safety_and_validation()
        self._validate_next_step()
        self._validate_missing_information()

    def _validate_intent(self):
        if not isinstance(self.intent, Intent):
            raise ErrResponseIntentInvalidType

    def _validate_user_goal(self):
        if not isinstance(self.user_goal, UserGoal):
            raise ErrResponseUserGoalInvalidType

    def _validate_mcp_routing(self):
        if not isinstance(self.mcp_routing, MCPRouting):
            raise ErrResponseMcpRoutingInvalidType

    def _validate_task_category(self):
        if not isinstance(self.task_category, TaskCategory):
            raise ErrResponseTaskCategoryInvalidType

    def _validate_actions(self):
        for action in self.actions:
            if not isinstance(action, Action):
                raise ErrResponseActionInvalidType

    def _validate_constraints(self):
        if self.constraints is not None and not isinstance(self.constraints, Constraints):
            raise ErrResponseConstraintsInvalidType

    def _validate_safety_and_validation(self):
        if self.safety_and_validation is not None and not isinstance(
            self.safety_and_validation, SafetyAndValidation
        ):
            raise ErrResponseSafetyInvalidType

    def _validate_next_step(self):
        if self.next_step is not None and not isinstance(self.next_step, NextStep):
            raise ErrResponseNextStepInvalidType

    def _validate_missing_information(self):
        if not isinstance(self.missing_information, list):
            raise ErrResponseMissingInformationInvalidType

        for item in self.missing_information:
            if not isinstance(item, str) or not item.strip():
                raise ErrResponseMissingInformationEmptyValue
    '''
    # -----------------------------
    # Aggregate Behavior
    # -----------------------------
    def is_executable(self) -> bool:
        """
        Returns True if the full response is ready for execution.
        """
        if self.safety_and_validation and self.safety_and_validation.requires_confirmation:
            return False

        if self.missing_information:
            return False

        if self.next_step:
            ready_to_execute = self.next_step.ready_to_execute
            if ready_to_execute and ready_to_execute.get_value() is False:
                return False

        return True

    def is_safe(self) -> bool:
        if not self.safety_and_validation:
            return True
        return not self.safety_and_validation.sensitive

    def requires_user_input(self) -> bool:
        if self.missing_information:
            return True

        if self.next_step and self.next_step.request_user_input and self.next_step.request_user_input.get_length() > 0:
            return True

        return False

    def add_missing_information(self, info: str) -> None:
        if not isinstance(info, str) or not info.strip():
            raise ErrResponseMissingInformationEmptyValue

        self.missing_information = create_missing_information(field_value=info, why_needed_value="", blocking_value="")

    def clear_missing_information(self) -> None:
        self.missing_information = None


def _build_response(response_ai: Dict[str, Any], tokens_usage_output: Dict[str, Any]) -> Response:

    intent: Optional[Intent] = None
    if "intent" in response_ai:
        primary = ""
        secondary = []
        confidence = 0.0
        if "primary" in response_ai["intent"]:
            primary = response_ai["intent"]["primary"]
        if "secondary" in response_ai["intent"]:
            secondary = response_ai["intent"]["secondary"]
        if "confidence" in response_ai["intent"]:
            confidence = response_ai["intent"]["confidence"]

        intent = create_intent(primary=primary, secondary=secondary, confidence=confidence)

    user_goal: Optional[UserGoal] = None
    if "user_goal" in response_ai:
        summary = ""
        expected_outcome = ""
        if "summary" in response_ai["user_goal"]:
            summary = response_ai["user_goal"]["summary"]
        if "expected_outcome" in response_ai["user_goal"]:
            expected_outcome = response_ai["user_goal"]["expected_outcome"]

        user_goal = create_user_goal(
            summary_value=summary,
            expected_outcome_value=expected_outcome,
        )


    mcp_routing: Optional[MCPRouting] = None
    if "mcp_routing" in response_ai and "required_servers" in response_ai["mcp_routing"]:
        required_servers = []
        required_servers = response_ai["mcp_routing"]["required_servers"]

        mcp_routing = create_mcp_routing(required_servers=required_servers)

    task_category: Optional[TaskCategory] = None
    if "task_category" in response_ai:        
        domain = ""
        type = ""
        complexity = ""

        if "domain" in response_ai["task_category"]:
            domain = response_ai["task_category"]["domain"]
        if "type" in response_ai["task_category"]:
            type = response_ai["task_category"]["type"]
        if "complexity" in response_ai["task_category"]:
            complexity = response_ai["task_category"]["complexity"]

        task_category = create_task_category(
            domain_value=domain,
            type_value=type,
            complexity_value=complexity,
        )


    actions: Optional[List[Action]] = None
    if "actions" in response_ai:
        actions = []
        for action in response_ai["actions"]:

            id = ""
            description = ""
            action_type = ""
            mcp_context_server_id = ""
            mcp_context_tool_name = ""
            mcp_context_parameters = {}
            dependencies = []
            required_inputs = []
            output = ""
            error = ""

            if "id" in action:
                id = action["id"]
            if "description" in action:
                description = action["description"]
            if "action_type" in action:
                action_type = action["action_type"]

            if "mcp_context" in action and action["mcp_context"] is not None:
                if "server_id" in action["mcp_context"]:
                    mcp_context_server_id = action["mcp_context"]["server_id"]
                if "tool_name" in action["mcp_context"]:
                    mcp_context_tool_name = action["mcp_context"]["tool_name"]
                if "parameters" in action["mcp_context"]:
                    mcp_context_parameters = action["mcp_context"]["parameters"]
            if "dependencies" in action:
                dependencies = action["dependencies"]
            if "required_inputs" in action:
                required_inputs = action["required_inputs"]
            if "output" in action:
                output = action["output"]
            if "error" in action:
                error = action["error"]
            

            action = create_action(
                id_value=id,
                description_value=description,
                action_type_value=action_type,
                mcp_context_server_id=mcp_context_server_id,
                mcp_context_tool_name=mcp_context_tool_name,
                mcp_context_parameters=mcp_context_parameters,
                dependencies_list=dependencies,
                required_inputs_list=required_inputs,
                output_value=output,
                error_value=error,
            )
            actions.append(action)
        
    missing_information: Optional[MissingInformation] = None
    if "missing_information" in response_ai and response_ai["missing_information"] is not None and len(response_ai["missing_information"]) > 0:
        missing_information = create_missing_information(
            field_value=response_ai["missing_information"]["field"],
            why_needed_value=response_ai["missing_information"]["why_needed"],
            blocking_value=response_ai["missing_information"]["blocking"],
        )
        
    
    constraints: Optional[Constraints] = None
    if "constraints" in response_ai and response_ai["constraints"] is not None:
        format = ""
        language = ""
        tone = ""
        length = "short"
        
        if "format" in response_ai["constraints"]:
            format = response_ai["constraints"]["format"]
        if "language" in response_ai["constraints"]:
            language = response_ai["constraints"]["language"]
        if "tone" in response_ai["constraints"]:
            tone = response_ai["constraints"]["tone"]
        if "length" in response_ai["constraints"]:
            length = response_ai["constraints"]["length"]

        constraints = create_constraints(format=format, language=language, tone=tone, length=length)


    safety_and_validation: Optional[SafetyAndValidation] = None
    if "safety_and_validation" in response_ai:
        sensitive = False
        requires_confirmation = False
        if "sensitive" in response_ai["safety_and_validation"]:
            sensitive = response_ai["safety_and_validation"]["sensitive"]
        if "requires_confirmation" in response_ai["safety_and_validation"]:
            requires_confirmation = response_ai["safety_and_validation"]["requires_confirmation"]

        safety_and_validation = create_safety_and_validation(
            sensitive_value=sensitive,
            requires_confirmation_value=requires_confirmation,
        )


    next_step: Optional[NextStep] = None
    if "next_step" in response_ai:
        ready_to_execute = False
        status = ""
        recomended_action = ""
        blocking_reason = ""
        request_user_input = []
        if "ready_to_execute" in response_ai["next_step"]:
            ready_to_execute = response_ai["next_step"]["ready_to_execute"]
        if "status" in response_ai["next_step"]:
            status = response_ai["next_step"]["status"]
        if "recommended_action" in response_ai["next_step"]:
            recomended_action = response_ai["next_step"]["recommended_action"]
        if "blocking_reason" in response_ai["next_step"]:
            blocking_reason = response_ai["next_step"]["blocking_reason"]
        if "request_user_input" in response_ai["next_step"]:
            request_user_input = response_ai["next_step"]["request_user_input"]
        
        next_step = create_next_step(
            ready_to_execute_value=ready_to_execute,
            status_value=status,
            recommended_action_value=recomended_action,
            blocking_reason_value=blocking_reason,
            request_user_input_value=request_user_input,
        )


    tokens_usage: TokensUsage = create_tokens_usage(
        prompt_tokens=tokens_usage_output["prompt_tokens"],
        completion_tokens=tokens_usage_output["completion_tokens"],
        total_tokens=tokens_usage_output["total_tokens"],
    )
   

    response = Response(
        intent=intent,
        user_goal=user_goal,
        mcp_routing=mcp_routing,
        task_category=task_category,
        actions=actions,
        missing_information=missing_information,
        constraints=constraints,
        safety_and_validation=safety_and_validation,
        next_step=next_step,
        tokens_usage=tokens_usage
    )

    return response