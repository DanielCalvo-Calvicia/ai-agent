# ===============================================
#  PIPELINE
#  The orchestrator: runs the steps of a flow in order and stops to
#  ask the user when a step leaves the flow waiting. The next
#  message of the user is checked as the answer, and the flow
#  continues from the step that was waiting.
#  It knows nothing about a particular agent: the steps, the jumps and the
#  result come from the Flow it is given.
# ===============================================

from typing import List, Optional

from application.orchestration.engine.answer_check import ANSWERED, CONFIRMED, DECLINED, STOP, AnswerChecker
from application.orchestration.engine.clarification import Clarifier
from application.orchestration.support.failure import AgentFailure, max_attempts
from application.orchestration.engine.flow import Flow, FlowContext
from application.orchestration.state.flow_state import FlowState
from application.orchestration.support.mcp_servers import server_names
from application.orchestration.support.metrics import SessionMetrics
from application.orchestration.state.paused_run import CONFIRMATION, INPUT, FlowResult, PausedRun
from application.orchestration.phases.phase import Step
from application.orchestration.engine.phase_runner import PhaseRunner
from application.outbound.ports.llm_ports import LLMOutboundPort
from application.outbound.ports.mcp_ports import McpToolsPort
from domain.value_objects.message import Message
from domain.value_objects.motion.robot_context import RobotContext
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
    ) -> None:
        runner = PhaseRunner(outbound_port, metrics, server_names(mcp_list))
        self.flow = flow
        self.steps = flow.build_steps(FlowContext(runner, mcp_list, mcp_tools))
        self.clarifier = Clarifier(runner)
        self.answer_checker = AnswerChecker(runner)

    def run(
        self,
        message: str,
        history: Optional[List[Message]] = None,
        paused: Optional[PausedRun] = None,
        robot_context: Optional[RobotContext] = None,
    ) -> FlowResult:
        """
        A new message runs through every step. When a run is waiting for the user, the message
        is treated as the reply to its question instead. `robot_context` is what motion-flow decided
        for this message (conversation-flow only).
        """
        if paused is not None:
            return self._resume(paused, message, list(history or []), robot_context)

        state = self.flow.new_state(message, list(history or []))
        state.robot_context = robot_context
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
                kind = CONFIRMATION if state.needs_confirmation() else INPUT
                question = self.clarifier.ask(state)
                return FlowResult(
                    reply=question,
                    paused=PausedRun(state, index, kind, question, self.clarifier.required_inputs(state)),
                )

            jump_to = self.flow.jump_after(step, state) if self.flow.jump_after else None
            if jump_to is not None:
                index = self._index_of(jump_to)
                continue

            index += 1

        return self.flow.build_result(state)

    def _index_of(self, step_name: str) -> int:
        return next(i for i, step in enumerate(self.steps) if step.name == step_name)

    # -----------------------------------------------
    #  RESUME
    # -----------------------------------------------

    def _resume(self, paused: PausedRun, message: str, history: List[Message],
                robot_context: Optional[RobotContext] = None) -> FlowResult:
        check = self.answer_checker.check(paused, message)
        paused.state.robot_context = robot_context

        if check.verdict == STOP:
            return FlowResult(STOPPED_TEXT)

        if check.verdict == DECLINED:
            return FlowResult(DECLINED_TEXT)

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

        return FlowResult(check.message, paused)                        # not an answer: ask again, keep waiting

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
