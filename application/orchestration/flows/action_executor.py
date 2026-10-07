# ===============================================
#  ACTION EXECUTOR
#  Runs the planned actions in dependency order, one LLM call each.
#
#  An action is ready when all its subactions and all the actions it depends
#  on are settled (done or failed). It receives their outputs. Its type picks
#  the prompt: an MCP tool call (phase 5, then phase 6 cleans the result) or
#  any other work (phase 4). Results are shared by every action, whatever its type.
# ===============================================

import contextvars
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from application.orchestration.support.action_tree import (
    BLOCKED_BY_CONFIRMATION,
    MCP_ACTION_TYPE,
    action_type_of,
    in_execution_order,
    subactions_of,
)
from application.orchestration.support.failure import AgentFailure, max_attempts
from application.orchestration.state.flow_state import FlowState
from application.orchestration.phases.phase import ActionPhaseSpec
from application.orchestration.engine.phase_runner import PhaseRunner
from application.orchestration.phases.special import cognitive_worker, mcp_operator
from application.orchestration.phases.special.cognitive_worker import COGNITIVE_WORKER
from application.orchestration.phases.special.data_engineer import DATA_ENGINEER
from application.orchestration.phases.special.mcp_operator import MCP_OPERATOR
from application.outbound.ports.mcp_ports import McpToolsPort
from domain.entities.llm_response.action import Action
from domain.value_objects.llm_response.action.output import create_output
from shared_logging import get_logger

logger = get_logger(__name__)

PARALLEL_VARIABLE = "AI_AGENT_PARALLEL_ACTIONS"

NO_RESULT = "The step did not produce a result."
UNRESOLVABLE = "The step could not run: circular or unknown dependencies."


class ActionExecutor:
    def __init__(self, runner: PhaseRunner, mcp_list: list, mcp_tools: Optional[McpToolsPort] = None) -> None:
        self.runner = runner
        self.mcp_list = mcp_list
        self.mcp_tools = mcp_tools

    def run(self, state: FlowState) -> None:
        if not state.actions:
            return

        pending = in_execution_order(state.actions)
        for action in pending:
            # The planner writes what it expects here. The real results replace it.
            action.output = None
            action.error = None
        known_ids = {a.id.get_value() for a in pending}
        outputs: Dict[str, str] = {}      # id -> output of the actions that worked
        failures: Dict[str, str] = {}     # id -> why the actions that did not work failed

        while pending:
            ready = [a for a in pending if self._is_ready(a, known_ids, outputs, failures)]

            if not ready:
                for action in pending:
                    self._fail(action, UNRESOLVABLE, failures)
                return

            self._settle_all(ready, state, known_ids, outputs, failures)
            for action in ready:
                pending.remove(action)

    def _settle_all(self, ready: List[Action], state: FlowState, known_ids: set,
                    outputs: Dict[str, str], failures: Dict[str, str]) -> None:
        """
        The ready actions do not need each other, so up to AI_AGENT_PARALLEL_ACTIONS of them run at the same time.
        MCP tool calls always run one by one, after the others. With 1 (the default) every action runs in plan order.
        """
        limit = parallel_actions()
        together = [a for a in ready if action_type_of(a) != MCP_ACTION_TYPE] if limit > 1 else []
        if len(together) > 1:
            with ThreadPoolExecutor(max_workers=min(limit, len(together))) as pool:
                futures = [pool.submit(contextvars.copy_context().run, self._settle, a, state, known_ids, outputs, failures)
                           for a in together]
                for future in futures:
                    future.result()
        one_by_one = [a for a in ready if len(together) <= 1 or all(a is not t for t in together)]
        for action in one_by_one:
            self._settle(action, state, known_ids, outputs, failures)

    # -----------------------------------------------
    #  ORDER
    # -----------------------------------------------

    def _inputs_of(self, action: Action) -> List[str]:
        """Ids whose result the action needs: its subactions and its declared dependencies."""
        ids = [sub.id.get_value() for sub in subactions_of(action)]
        if action.dependencies:
            ids.extend(action.dependencies.get_value())
        return ids

    def _is_ready(self, action: Action, known_ids: set, outputs: Dict[str, str], failures: Dict[str, str]) -> bool:
        """Unknown ids count as settled: they will never finish, and _settle fails the action for them."""
        return all(i in outputs or i in failures or i not in known_ids for i in self._inputs_of(action))

    # -----------------------------------------------
    #  ONE ACTION
    # -----------------------------------------------

    def _settle(
        self,
        action: Action,
        state: FlowState,
        known_ids: set,
        outputs: Dict[str, str],
        failures: Dict[str, str],
    ) -> None:
        unknown = [i for i in self._inputs_of(action) if i not in known_ids]
        if unknown:
            self._fail(action, f"The step depends on unknown steps: {', '.join(unknown)}.", failures)
            return

        failed_inputs = [i for i in self._inputs_of(action) if i in failures]
        if failed_inputs:
            self._fail(action, f"The step was skipped because a step it needs failed: {', '.join(failed_inputs)}.", failures)
            return

        dependency_outputs = {i: outputs[i] for i in (action.dependencies.get_value() if action.dependencies else [])}
        subaction_outputs = {sub.id.get_value(): outputs[sub.id.get_value()] for sub in subactions_of(action)}

        try:
            if action_type_of(action) == MCP_ACTION_TYPE:
                output, error = self._run_mcp(action, state, dependency_outputs, subaction_outputs)
            else:
                output, error = self._run_worker(action, state, dependency_outputs, subaction_outputs)
        except AgentFailure as failure:
            output, error = "", failure.explanation()

        if output:
            self._succeed(action, output, outputs)
        else:
            self._fail(action, error or NO_RESULT, failures)

    def _run_worker(self, action, state, dependency_outputs, subaction_outputs) -> tuple:
        extra = cognitive_worker.build_extra(state, dependency_outputs, subaction_outputs)
        return self._ask(action, COGNITIVE_WORKER, extra)

    def _run_mcp(self, action, state, dependency_outputs, subaction_outputs) -> tuple:
        if state.requires_confirmation():
            return "", BLOCKED_BY_CONFIRMATION

        extra = mcp_operator.build_extra(state, self.mcp_list, self.mcp_tools, dependency_outputs, subaction_outputs)

        output, error = "", ""
        for attempt in range(max_attempts()):
            output, error = self._ask(action, MCP_OPERATOR, extra, tools=self.mcp_list)
            if output:
                break
            logger.warning("MCP action did not produce a result", action_id=action.id.get_value(), attempt=attempt + 1)

        if not output:
            return "", error

        # The raw result of a tool is cleaned before other actions use it.
        return self._normalize(action, output), ""

    def _normalize(self, action: Action, output: str) -> str:
        _set_output(action, output)   # so the data engineer sees the raw result in the action
        response = self.runner.run_action(
            action=action,
            spec=DATA_ENGINEER,
            user_message_extra={},
            action_id=action.id.get_value(),
        )
        cleaned = response.actions[0].output.get_value() if response.actions and response.actions[0].output else ""
        return cleaned or output

    def _ask(self, action: Action, spec: ActionPhaseSpec, extra: Dict[str, Any], tools: Optional[list] = None) -> tuple:
        """One LLM call for the action. Returns (output, error) as the LLM wrote them."""
        response = self.runner.run_action(
            action=action,
            spec=spec,
            user_message_extra=extra,
            tools=tools,
            action_id=action.id.get_value(),
        )
        if not response.actions:
            return "", ""

        answer = response.actions[0]
        return (
            answer.output.get_value() if answer.output else "",
            answer.error.get_value() if answer.error else "",
        )

    # -----------------------------------------------
    #  RESULT
    # -----------------------------------------------

    @staticmethod
    def _succeed(action: Action, output: str, outputs: Dict[str, str]) -> None:
        _set_output(action, output)
        outputs[action.id.get_value()] = output

    @staticmethod
    def _fail(action: Action, error: str, failures: Dict[str, str]) -> None:
        action.mark_failed(error)
        failures[action.id.get_value()] = error


def parallel_actions() -> int:
    """How many independent actions may run at the same time (1 = one after another)."""
    try:
        return max(1, int(os.environ.get(PARALLEL_VARIABLE, "1")))
    except ValueError:
        return 1


def _set_output(action: Action, output: str) -> None:
    try:
        action.mark_success(output)
    except Exception:
        # The action already carries an error from the plan. Keep the result anyway.
        action.output = create_output(output)
