# ===============================================
#  ROUTER
#  Runs one user message through the agents: the identification flow first (triage), then the one flow that
#  answers, chosen by task_category.domain:
#
#      communication -> conversation   (a plain reply)
#      movement      -> movement       (arm movements)
#      anything else -> special        (plan, check, execute, write)
#
#  The chosen flow starts from the state identification left, so nothing is classified twice. A flow that stopped to
#  ask the user a question is resumed by the next message, without identifying it again: the paused run says which
#  flow it belongs to. The flows never call each other; only the router moves a message from one to the next.
#
#  After the conversation or the special flow has written its reply, the router runs the expression flow on it: the
#  emotion of the exchange becomes an arm gesture that goes with the reply. A reply the user asked movements for
#  (the movement flow) gets none: the robot does what was asked.
# ===============================================

from typing import Dict, List, Optional

from application.orchestration.engine.flow import Flow
from application.orchestration.engine.pipeline import Pipeline
from application.orchestration.flows.conversation import CONVERSATION_FLOW
from application.orchestration.flows.expression import EXPRESSION_FLOW
from application.orchestration.flows.identification import IDENTIFICATION_FLOW
from application.orchestration.flows.movement import MOVEMENT_FLOW
from application.orchestration.flows.registry import FLOWS
from application.orchestration.flows.special import SPECIAL_FLOW
from application.orchestration.state.expression_state import ExpressionFlowState
from application.orchestration.state.flow_state import FlowState
from application.orchestration.state.motion_state import MotionFlowState
from application.orchestration.state.paused_run import FlowResult, PausedRun
from application.orchestration.support.expression_settings import expression_enabled, speech_seconds
from application.orchestration.support.metrics import SessionMetrics
from application.outbound.ports.llm_ports import LLMOutboundPort
from application.outbound.ports.mcp_ports import McpToolsPort
from domain.value_objects.llm_request.message import Message
from shared_logging import get_logger

logger = get_logger(__name__)

# task_category.domain -> the flow that answers. A domain that is not listed goes to SPECIAL_FLOW.
FLOW_BY_DOMAIN: Dict[str, Flow] = {
    "communication": CONVERSATION_FLOW,
    "movement": MOVEMENT_FLOW,
}
DEFAULT_FLOW = SPECIAL_FLOW

# The flows whose reply gets a gesture. The movement flow's does not: the user asked for movements, the robot does those.
EXPRESSIVE_FLOWS = (CONVERSATION_FLOW.name, SPECIAL_FLOW.name)


def flow_for(state: FlowState) -> Flow:
    """The flow that answers a message, from the domain the identification flow found."""
    domain = state.task_category.domain.get_value() if state.task_category and state.task_category.domain else None
    return FLOW_BY_DOMAIN.get(domain or "", DEFAULT_FLOW)


class AgentRouter:
    def __init__(
        self,
        outbound_port: LLMOutboundPort,
        mcp_list: list,
        metrics: SessionMetrics,
        mcp_tools: Optional[McpToolsPort] = None,
    ) -> None:
        self.pipelines: Dict[str, Pipeline] = {
            flow.name: Pipeline(outbound_port, mcp_list, metrics, mcp_tools, flow=flow) for flow in FLOWS
        }

    def run(
        self,
        message: str,
        history: Optional[List[Message]] = None,
        paused: Optional[PausedRun] = None,
        speak_movements: bool = True,
    ) -> FlowResult:
        """
        The reply, the movements and the run that is still waiting for the user (if any). `result.flow` says which
        flow produced it. `speak_movements` is Brain's setting: whether a movement that goes ahead is announced.
        """
        result = self._run(message, history, paused, speak_movements)
        return self._with_gesture(message, result)

    def _run(
        self,
        message: str,
        history: Optional[List[Message]],
        paused: Optional[PausedRun],
        speak_movements: bool,
    ) -> FlowResult:
        history = list(history or [])

        if paused is not None:
            if isinstance(paused.state, MotionFlowState):
                paused.state.speak_movements = speak_movements       # Brain's setting of this message, not of the one that paused
            result = self.pipelines[paused.flow].run(message, history, paused)
            if paused.flow != IDENTIFICATION_FLOW.name or result.paused or result.ended_early or result.state is None:
                return result
            return self._answer(result.state, history, speak_movements)

        result = self.pipelines[IDENTIFICATION_FLOW.name].run(message, history)
        if result.paused or result.state is None:
            return result                                            # triage needs a detail first

        return self._answer(result.state, history, speak_movements)

    def _with_gesture(self, message: str, result: FlowResult) -> FlowResult:
        """
        Gives the reply an arm gesture, the emotion of the exchange (`message` and the reply) made into random movements.
        The reply is never held back by it: when the expression flow fails or makes nothing, the result is the one it got.
        """
        if (not expression_enabled() or result.flow not in EXPRESSIVE_FLOWS or result.ended_early
                or result.movements or not result.reply.strip()):
            return result

        try:
            state = ExpressionFlowState(message=message, reply=result.reply, speech_seconds=speech_seconds(result.reply))
            gesture = self.pipelines[EXPRESSION_FLOW.name].run(message, [], state=state)
        except Exception as error:
            logger.warning("No gesture for this reply: the expression flow failed", error_type=type(error).__name__)
            return result

        if gesture.movements:
            logger.info("Gesture for the reply", emotion=state.emotion, intensity=state.intensity,
                        movements=len(gesture.movements))
            result.movements = gesture.movements
            result.gesture = True
        return result

    def _answer(self, identified: FlowState, history: List[Message], speak_movements: bool) -> FlowResult:
        """Hands the identified message to the flow that answers it."""
        flow = flow_for(identified)
        logger.info("Routing message", flow=flow.name,
                    domain=identified.task_category.domain.get_value() if identified.task_category else "")

        state = flow.new_state(identified.message, history)
        state.take_over(identified)
        if isinstance(state, MotionFlowState):
            state.speak_movements = speak_movements

        return self.pipelines[flow.name].run(identified.message, history, state=state)
