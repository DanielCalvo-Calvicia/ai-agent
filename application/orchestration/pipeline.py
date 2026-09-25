# ===============================================
#  PIPELINE
#  The orchestrator: runs the steps in order and stops to
#  ask the user when a step leaves the flow waiting. The next
#  message of the user is checked as the answer, and the flow
#  continues from the step that was waiting.
# ===============================================

from typing import List, Optional

from application.orchestration.action_executor import ActionExecutor
from application.orchestration.answer_check import ANSWERED, CONFIRMED, DECLINED, STOP, AnswerChecker
from application.orchestration.clarification import Clarifier
from application.orchestration.failure import AgentFailure, max_attempts
from application.orchestration.fast_path import applies as fast_path_applies
from application.orchestration.flow_state import FlowState
from application.orchestration.mcp_servers import server_names
from application.orchestration.metrics import SessionMetrics
from application.orchestration.paused_run import CONFIRMATION, INPUT, FlowResult, PausedRun
from application.orchestration.phase import PhaseSpec, Step
from application.orchestration.phase_runner import PhaseRunner
from application.orchestration.phases.draft_writer import DRAFT_WRITER
from application.orchestration.phases.editor_in_chief import EDITOR_IN_CHIEF
from application.orchestration.phases.project_manager import make_project_manager
from application.orchestration.phases.safety_gate import SAFETY_GATE
from application.orchestration.phases.triage import TRIAGE
from application.orchestration.robot_directive import find_directive
from application.outbound.ports.llm_ports import LLMOutboundPort
from application.outbound.ports.mcp_ports import McpToolsPort
from domain.value_objects.message import Message
from shared_logging import get_logger

logger = get_logger(__name__)

STOPPED_TEXT = "Okay, I stopped that. What would you like to do next?"
DECLINED_TEXT = "Okay, I will not do that."

TRIAGE_STEP_NAME = "triage_specialist"
DRAFT_WRITER_STEP_NAME = "draft_writer"


def _needs_user_input(state: FlowState) -> bool:
    return state.needs_user_input()


def build_steps(runner: PhaseRunner, executor: ActionExecutor, mcp_list: list, mcp_tools: Optional[McpToolsPort]) -> List[Step]:
    """The phases of the agent, in execution order."""

    def llm_phase(spec: PhaseSpec):
        return lambda state: spec.apply(state, runner.run_phase(spec, state))

    return [
        # 1 - Classifies intent, extracts user goal and task category.
        Step(TRIAGE_STEP_NAME, llm_phase(TRIAGE), pause_if=_needs_user_input, phase_id=1, retry_on_status=True),
        # 2 - Decomposes the goal into actions and identifies required inputs per action.
        Step("project_manager", llm_phase(make_project_manager(mcp_list, mcp_tools)), pause_if=_needs_user_input,
             phase_id=2, retry_on_status=True),
        # 3 - Validates actions for safety and decides if user confirmation is needed.
        Step("safety_quality_gatekeeper", llm_phase(SAFETY_GATE), pause_if=_needs_user_input,
             phase_id=3, retry_on_status=True),
        # 4, 5, 6 - Every action runs in dependency order, one LLM request each:
        #           the worker (4), the MCP operator (5) and, for MCP results, the data engineer (6).
        Step("action_executor", executor.run),
        # 7 - Synthesizes all action outputs into a first draft of the user response.
        # The fast path (below) jumps straight here from triage for a plain, simple reply, skipping
        # 2/3/4-6: nothing was planned, so there is nothing to validate or execute.
        Step(DRAFT_WRITER_STEP_NAME, llm_phase(DRAFT_WRITER)),
        # 8 - Polishes the draft and produces the final response for the user.
        Step("editor_in_chief", llm_phase(EDITOR_IN_CHIEF), phase_id=8, retry_on_status=True),
    ]


class Pipeline:
    def __init__(
        self,
        outbound_port: LLMOutboundPort,
        mcp_list: list,
        metrics: SessionMetrics,
        mcp_tools: Optional[McpToolsPort] = None,
    ) -> None:
        runner = PhaseRunner(outbound_port, metrics, server_names(mcp_list))
        executor = ActionExecutor(runner, mcp_list, mcp_tools)
        self.steps = build_steps(runner, executor, mcp_list, mcp_tools)
        self._draft_writer_index = next(i for i, s in enumerate(self.steps) if s.name == DRAFT_WRITER_STEP_NAME)
        self.clarifier = Clarifier(runner)
        self.answer_checker = AnswerChecker(runner)

    def run(
        self,
        message: str,
        history: Optional[List[Message]] = None,
        paused: Optional[PausedRun] = None,
    ) -> FlowResult:
        """
        A new message runs through every step. When a run is waiting for the user, the message
        is treated as the reply to its question instead.
        """
        if paused is not None:
            return self._resume(paused, message, list(history or []))

        return self._run_from(0, FlowState(message=message, history=list(history or [])))

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

            if step.name == TRIAGE_STEP_NAME and fast_path_applies(state):
                logger.info("Fast path: skipping planning and action execution for a simple reply")
                index = self._draft_writer_index
                continue

            index += 1

        return FlowResult(reply=state.final_text(), directive=find_directive(state.actions))

    # -----------------------------------------------
    #  RESUME
    # -----------------------------------------------

    def _resume(self, paused: PausedRun, message: str, history: List[Message]) -> FlowResult:
        check = self.answer_checker.check(paused, message)

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
