from dataclasses import dataclass, field
import json
from typing import Dict, List, Optional

from domain.value_objects.action.id import Id as ActionId, create_id
from domain.value_objects.action.description import Description as ActionDescription, create_description
from domain.value_objects.action.action_type import ActionType, create_action_type
from domain.value_objects.action.mcp_context import McpContext as ActionMcpContext, create_mcp_context
from domain.value_objects.action.dependencies import Dependencies as ActionDependencies, create_dependencies
from domain.value_objects.action.required_inputs import RequiredInputs as ActionRequiredInputs, create_required_inputs
from domain.value_objects.action.output import Output as ActionOutput, create_output
from domain.value_objects.action.error import Error as ActionError, create_error

ErrActionCantMarkSuccessWhenHasError = RuntimeError("Cannot mark success when action has error.")
ErrActionOutputEmptyWhenSuccess = ValueError("output cannot be empty on success.")

schema_full_path = "schema/response/advanced/actions/actions.schema.json"
schema_base_path = "schema/response/advanced/actions/actions.base.schema.json"
schema_items_path = "schema/response/advanced/actions/actions.item.schema.json" 


@dataclass
class Action:
    id: ActionId
    description: ActionDescription
    action_type: Optional[ActionType]
    mcp_context: Optional[ActionMcpContext]
    dependencies: Optional[ActionDependencies]
    required_inputs: Optional[ActionRequiredInputs]
    output: Optional[ActionOutput]
    error: Optional[ActionError]
    subtasks: Optional[Dict[str, Action]] = None


    # ---------------------------
    # Initialization & Invariants
    # ---------------------------
    def __post_init__(self):
        self.validate()

    def validate(self):
        self._validate_identity()
        self._validate_core_fields()
        self._validate_collections()

    def _validate_identity(self):
        self.id.validate()

    def _validate_core_fields(self):
        self.description.validate()
        if self.action_type:
            self.action_type.validate()
        if self.mcp_context:
            self.mcp_context.validate()

    def _validate_collections(self):
        #self.required_inputs.validate()
        pass

    # ---------------------------
    # Identity Equality (Entity rule)
    # ---------------------------
    def __eq__(self, other):
        if not isinstance(other, Action):
            return False
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

    # ---------------------------
    # Domain Behavior
    # ---------------------------
    def mark_success(self, output: str) -> None:
        if self.error:
            raise ErrActionCantMarkSuccessWhenHasError
        if not output.strip():
            raise ErrActionOutputEmptyWhenSuccess
        self.output = create_output(output)
        self.error = None

    def mark_failed(self, error: str) -> None:
        self.error = create_error(error)

    def add_dependency(self, dependency_id: str) -> None:
        if self.dependencies:
            self.dependencies.add_dependency(dependency_id)

    def add_required_input(self, input_name: str) -> None:
        if self.required_inputs:
            self.required_inputs.add_required_input(input_name)

    def clear_error(self) -> None:
        self.error = None

    # ---------------------------
    # State Queries
    # ---------------------------
    def is_successful(self) -> bool:
        return bool(self.output) and not self.error

    def is_failed(self) -> bool:
        return bool(self.error)

    def is_pending(self) -> bool:
        return not self.output and not self.error

    def has_dependencies(self) -> bool:
        if not self.dependencies:
            return False
        return self.dependencies.get_length() > 0

    def requires_input(self) -> bool:
        if not self.required_inputs:
            return False
        return self.required_inputs.get_length() > 0
    
def create_action(
    id_value: str,
    description_value: str,
    action_type_value: Optional[str] = None,
    mcp_context_server_id: Optional[str] = None,
    mcp_context_tool_name: Optional[str] = None,
    mcp_context_parameters: Optional[dict] = None,
    dependencies_list: Optional[List[str]] = None,
    required_inputs_list: Optional[List[str]] = None,
    output_value: Optional[str] = None,
    error_value: Optional[str] = None,
) -> Action:
    
    id = create_id(id_value)
    description = create_description(description_value)
    action_type: Optional[ActionType] = None
    if action_type_value and action_type != "":
        action_type = create_action_type(action_type_value)

    mcp_context: Optional[ActionMcpContext] = None
    if mcp_context_server_id and mcp_context_tool_name and mcp_context_parameters:
        mcp_context = create_mcp_context(
            server_id=mcp_context_server_id,
            tool_name=mcp_context_tool_name,
            parameters=mcp_context_parameters
        )

    dependencies: Optional[ActionDependencies] = None
    if dependencies_list and dependencies_list != []:
        dependencies = create_dependencies(dependencies_list or [])

    required_inputs: Optional[ActionRequiredInputs] = None
    if required_inputs_list and required_inputs_list != []:
        required_inputs = create_required_inputs(required_inputs_list or [])
    
    output: Optional[ActionOutput] = None
    if output_value and output_value != "":
        output = create_output(output_value)
    
    error: Optional[ActionError] = None
    if error_value and error_value != "":
        error = create_error(error_value)

    return Action(
        id=id,
        description=description,
        action_type=action_type,
        mcp_context=mcp_context,
        dependencies=dependencies,
        required_inputs=required_inputs,
        output=output,
        error=error
    )

def get_schema():
    # Load the schema from your local file
    with open(schema_full_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic

def get_base_schema():
    # Load the base schema from your local file
    with open(schema_base_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic

def get_items_schema():
    # Load the confidence schema from your local file
    with open(schema_items_path, 'r') as f:
        schema_dic = json.load(f)
    return schema_dic