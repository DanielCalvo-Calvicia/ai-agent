# ===============================================
#  PHASE RUNNER
#  The only place that builds an LLM payload, sends it
#  through LLMOutboundPort and records the token usage.
# ===============================================

import json
import time
from typing import Any, Dict, Optional, Sequence, Tuple

from application.orchestration.support.failure import AgentFailure, classify, max_attempts, worth_retrying
from application.orchestration.state.flow_state import FlowState
from application.orchestration.support.metrics import SessionMetrics
from application.orchestration.phases.phase import ActionPhaseSpec, PhaseSpec
from application.orchestration.support.schemas import actions_schema, object_schema
from application.outbound.ports.llm_ports import LLMOutboundPort
from application.orchestration.support.model_selection import model_for_phase
from application.system_prompts.general import build_system_prompt_from_file

from domain.entities.llm_response.action import Action
from domain.entities.llm_request.payload import Payload
from domain.entities.llm_response.response import Response
from domain.value_objects.llm_response.intent.intent import create_intent
from domain.value_objects.llm_request.max_tokens import create_max_tokens
from domain.value_objects.llm_request.message import Role, create_message
from domain.value_objects.llm_request.model import SelectedModel
from domain.value_objects.llm_request.response_format import ResponseFormat
from domain.value_objects.llm_request.temperature import create_temperature
from shared_logging import get_logger

logger = get_logger(__name__)

DEFAULT_TEMPERATURE = 1.0
DEFAULT_MAX_TOKENS = 10000


class PhaseRunner:
    def __init__(
        self,
        outbound_port: LLMOutboundPort,
        metrics: SessionMetrics,
        mcp_server_names: Sequence[str] = (),
    ) -> None:
        self.outbound_port = outbound_port
        self.metrics = metrics
        self.mcp_server_names = list(mcp_server_names)

    # -----------------------------------------------
    #  WHOLE-RESPONSE PHASES (1, 2, 3, 7, 8)
    # -----------------------------------------------

    def run_phase(self, spec: PhaseSpec, state: FlowState) -> Response:
        """One LLM call for the phase. The caller applies the response to the state."""
        model = model_for_phase(spec.id, spec.model)

        payload = _build_payload(
            prompt_file=spec.prompt_file,
            model=model,
            intent=spec.intent,
            user_message=_as_message_text(spec.build_input(state)),
            response_format=ResponseFormat(
                name=spec.format_name,
                schema=object_schema(spec.required, spec.properties()),
            ),
            tools=[],
        )

        return self.send(payload, spec.id, model)

    # -----------------------------------------------
    #  PER-ACTION PHASES (4, 5, 6)
    # -----------------------------------------------

    def run_action(
        self,
        action: Action,
        spec: ActionPhaseSpec,
        user_message_extra: Dict[str, Any],
        tools: Optional[list] = None,
        action_id: Optional[str] = None,
    ) -> Response:
        """
        One LLM call that processes a single action.
        The caller reads response.actions[0] for the processed result.
        """
        model = model_for_phase(spec.id, spec.model)

        payload = _build_payload(
            prompt_file=spec.prompt_file,
            model=model,
            intent=spec.intent,
            user_message={"action": action, **user_message_extra}.__str__(),
            response_format=ResponseFormat(
                name=spec.format_name,
                schema=object_schema(["actions"], {"actions": actions_schema(self.mcp_server_names, spec.schema_file)}),
            ),
            tools=tools if tools is not None else [],
        )

        return self.send(payload, spec.id, model, action_id=action_id)

    # -----------------------------------------------
    #  SEND
    # -----------------------------------------------

    def send(
        self,
        payload: Payload,
        phase_id: int,
        model: SelectedModel,
        action_id: Optional[str] = None,
    ) -> Response:
        """
        Asks the LLM and records the call in the metrics. A failed call is tried again (up to
        AI_AGENT_MAX_ATTEMPTS in total) unless the error cannot get better. When it still fails,
        an AgentFailure says what happened.
        """
        attempts = max_attempts()
        started_ns = time.time_ns()

        for attempt in range(1, attempts + 1):
            try:
                answer = self.outbound_port.ask(payload)
                if not isinstance(answer, Response):
                    raise TypeError("Invalid response type")
            except Exception as error:
                if attempt == attempts or not worth_retrying(error):
                    raise AgentFailure(classify(error), phase_id, error) from error
                logger.warning("LLM call failed, trying again", phase_id=phase_id, attempt=attempt,
                               error_type=type(error).__name__)
                continue

            self._track(answer, phase_id, model, action_id, payload, started_ns, time.time_ns())
            return answer

        raise AgentFailure("unknown", phase_id)       # not reached: the last attempt either answers or raises

    def _track(
        self,
        response: Response,
        phase_id: int,
        model: SelectedModel,
        action_id: Optional[str],
        payload: Optional[Payload] = None,
        started_ns: Optional[int] = None,
        ended_ns: Optional[int] = None,
    ) -> None:
        """Silently skips if the response carries no token usage data."""
        if response.tokens_usage:
            self.metrics.record(
                phase_id=phase_id,
                model=model.id,
                prompt=response.tokens_usage.prompt_tokens,
                completion=response.tokens_usage.completion_tokens,
                total=response.tokens_usage.total_tokens,
                action_id=action_id,
                input_text=_input_text(payload),
                output_text=_output_text(response),
                started_ns=started_ns,
                ended_ns=ended_ns,
            )


MAX_REPORTED_CHARS = 100_000


def _input_text(payload: Optional[Payload]) -> Optional[str]:
    """What was sent to the LLM: the system prompt and the message, as chat messages."""
    if payload is None:
        return None
    messages = ([{"role": payload.system_prompt.role.value, "content": payload.system_prompt.content}]
                if payload.system_prompt else [])
    messages.append({"role": payload.message.role.value, "content": payload.message.content})
    return json.dumps(messages, ensure_ascii=False)[:MAX_REPORTED_CHARS]


def _output_text(response: Response) -> Optional[str]:
    """What the LLM answered: its JSON object, or its text."""
    if response.raw is not None:
        return json.dumps(response.raw, ensure_ascii=False, default=str)[:MAX_REPORTED_CHARS]
    return response.text[:MAX_REPORTED_CHARS] if response.text else None


def _as_message_text(value: Any) -> str:
    return value if isinstance(value, str) else value.__str__()


def _build_payload(
    prompt_file: str,
    model: SelectedModel,
    intent: Tuple[str, Tuple[str, ...], float],
    user_message: str,
    response_format: ResponseFormat,
    tools: list,
) -> Payload:
    """The request every phase sends: same system prompt scheme and sampling, different content."""
    primary, secondary, confidence = intent

    return Payload(
        intent=create_intent(primary=primary, secondary=list(secondary), confidence=confidence),
        model=model,
        system_prompt=build_system_prompt_from_file(prompt_file),
        message=create_message(Role.USER, user_message),
        reasoning=None,
        temperature=create_temperature(DEFAULT_TEMPERATURE),
        top_p=None,
        seed=None,
        max_tokens=create_max_tokens(DEFAULT_MAX_TOKENS),
        response_format=response_format,
        tools=tools,
        metadata={},
    )
