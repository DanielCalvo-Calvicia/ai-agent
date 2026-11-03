# ===============================================
#  PIPELINE
#  The orchestrator: runs the steps of a flow in order and stops to
#  ask the user when a step leaves the flow waiting. The next
#  message of the user is checked as the answer, and the flow
#  continues from the step that was waiting.
#  It knows nothing about a particular flow: the steps, the jumps, the result and
#  the hooks for a question to the user (`on_pause`, `on_resume`) come from the Flow it is given.
# ===============================================

from typing import Dict, List, Mapping, Optional, Sequence

from application.engine.answer_check import ANSWERED, CONFIRMED, DECLINED, STOP, AnswerChecker
from application.engine.clarification import Clarifier
from application.engine.support.failure import AgentFailure, max_attempts
from application.engine.flow import Flow, FlowContext
from application.engine.state.flow_state import FlowState
from application.engine.support.mcp_servers import server_names
from application.engine.support.metrics import SessionMetrics
from application.engine.support.model_selection import ModelResolver
from application.engine.support.prompt_overrides import PromptOverride
from application.engine.state.paused_run import CONFIRMATION, INPUT, FlowResult, PausedRun
from application.steps.hooks import ANSWER_CHECKER, USER_CLARIFICATION
from application.steps.phase import Step
from application.engine.phase_runner import PhaseRunner
from application.outbound.ports.llm_ports import LLMOutboundPort
from application.outbound.ports.mcp_ports import McpToolsPort, ToolScope, scoped
from domain.value_objects.llm_request.message import Message
from shared_logging import get_logger

logger = get_logger(__name__)

STOPPED_TEXT = "Okay, I stopped that. What would you like to do next?"
DECLINED_TEXT = "Okay, I will not do that."


class Pipeline:
    def __init__(
        self,
        outbound_port: LLMOutboundPort,
        mcp_list: list,
        metrics: SessionMetrics,
        mcp_tools: Optional[McpToolsPort] = None,
        *,
        flow: Flow,
        models: Optional[ModelResolver] = None,
        tool_levels: Sequence[Optional[dict]] = (),
        tool_overrides: Optional[Dict[str, dict]] = None,
        prompts: Optional[Mapping[str, PromptOverride]] = None,
    ) -> None:
        """
        `tool_levels`: the `tools` of the profile (and of its entry for this flow), None where a level sets nothing. The tools a
        step may use are those every level allows (T-05.13): these, the flow file's, the step's in the flow file and the profile's
        `overrides.<step>.tools`. `mcp_list` is every configured server; a step is built with the ones it may use.
        """
        overrides = tool_overrides or {}

        def scope_of(step_name: Optional[str]) -> ToolScope:
            return ToolScope.of(*tool_levels, flow.tools, flow.step_tools.get(step_name) if step_name else None,
                                overrides.get(step_name) if step_name else None)

        self.scope_of = scope_of
        flow_servers, flow_tools = scoped(mcp_list, mcp_tools, scope_of(None))
        runner = PhaseRunner(outbound_port, metrics, server_names(flow_servers, flow_tools), models=models, flow_name=flow.name, prompts=prompts)
        self.flow = flow
        self.steps = flow.build_steps(FlowContext(runner, mcp_list, mcp_tools, scope_of))
        self.clarifier = Clarifier(runner)
        self.answer_checker = AnswerChecker(runner)

    def run(
        self,
        message: str,
        history: Optional[List[Message]] = None,
        paused: Optional[PausedRun] = None,
        state: Optional[FlowState] = None,
    ) -> FlowResult:
        """
        A new message runs through every step. When a run is waiting for the user, the message
        is treated as the reply to its question instead. `state` is a state prepared by the caller (the router
        hands over what the identification flow found out); without it the flow starts a fresh one.
        """
        if paused is not None:
            return self._resume(paused, message, list(history or []))

        if state is None:
            state = self.flow.new_state(message, list(history or []))
        return self._run_from(0, state)

    # -----------------------------------------------
    #  RUN AND PAUSE
    # -----------------------------------------------

    def _run_from(self, start: int, state: FlowState) -> FlowResult:
        index = start
        while index < len(self.steps):
            step = self.steps[index]
            self._run_step(step, state)

            if step.pause_if and step.pause_if(state):
                if self.flow.on_pause != USER_CLARIFICATION:
                    raise ValueError(f"flow {self.flow.name!r}: step {step.name!r} can ask the user, but the flow has no on_pause hook")
                kind = CONFIRMATION if state.needs_confirmation() else INPUT
                question = self.clarifier.ask(state)
                return self._tag(FlowResult(
                    reply=question,
                    paused=PausedRun(state, index, kind, question, self.clarifier.required_inputs(state),
                                     flow=self.flow.name),
                ), state)

            jump_to = self.flow.jump_after(step, state) if self.flow.jump_after else None
            if jump_to is not None:
                index = self._index_of(jump_to)
                continue

            index += 1

        return self._tag(self.flow.build_result(state), state)

    def _tag(self, result: FlowResult, state: FlowState) -> FlowResult:
        """Says which flow produced the result and with which state."""
        result.flow = self.flow.name
        result.state = state
        return result

    def _index_of(self, step_name: str) -> int:
        return next(i for i, step in enumerate(self.steps) if step.name == step_name)

    # -----------------------------------------------
    #  RESUME
    # -----------------------------------------------

    def _resume(self, paused: PausedRun, message: str, history: List[Message]) -> FlowResult:
        if self.flow.on_resume != ANSWER_CHECKER:
            raise ValueError(f"flow {self.flow.name!r} has no on_resume hook: it cannot be resumed")
        check = self.answer_checker.check(paused, message)

        if check.verdict == STOP:
            return self._tag(FlowResult(STOPPED_TEXT, ended_early=True), paused.state)

        if check.verdict == DECLINED:
            return self._tag(FlowResult(DECLINED_TEXT, ended_early=True), paused.state)

        if check.verdict == ANSWERED:
            state = paused.state
            state.history = history
            state.add_answer(paused.question, check.answer or message)
            return self._run_from(paused.step_index, state)             # the step that waited runs again, now with the answer

        if check.verdict == CONFIRMED:
            state = paused.state
            state.history = history
            state.confirm()
            return self._run_from(paused.step_index + 1, state)         # the plan was accepted: go on after the safety gate

        return self._tag(FlowResult(check.message, paused), paused.state)   # not an answer: ask again, keep waiting

    @staticmethod
    def _run_step(step: Step, state: FlowState) -> None:
        """Runs the step. A step whose answer says "retry" or "error" is run again, up to AI_AGENT_MAX_ATTEMPTS."""
        attempts = max_attempts()

        for attempt in range(1, attempts + 1):
            step.run(state)
            if not (step.retry_on_status and state.next_step_says_retry()):
                return
            logger.warning("Step reported retry or error", step=step.name, attempt=attempt)

        raise AgentFailure("reported_error", step.phase_id)
