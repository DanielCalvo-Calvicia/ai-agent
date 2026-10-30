# ===============================================
#  FAILURE
#  What went wrong during a message, and the apology that tells the user
#  what happened and why. The apology is a template (not an LLM call),
#  so it still works when the LLM is the thing that failed.
#  It never includes raw error text: that can hold request details.
# ===============================================

import os
import time
from typing import Optional

from shared_logging import get_logger

logger = get_logger(__name__)

# One setting for every "try again" of the agent: LLM calls, MCP tool calls, status `retry`.
DEFAULT_MAX_ATTEMPTS = 3
MAX_ATTEMPTS_VARIABLE = "AI_AGENT_MAX_ATTEMPTS"

# Seconds to wait before the second try of an LLM call that failed for lack of capacity; it doubles on every try (up to 8 times
# this value) and is not spent at all when the provider says a daily quota is used up. 0 = no wait.
DEFAULT_RETRY_WAIT_SECONDS = 1.0
RETRY_WAIT_VARIABLE = "AI_AGENT_RETRY_WAIT_SECONDS"

# How many MCP tool actions one message may run (0 = no limit).
DEFAULT_MAX_MCP_CALLS = 5
MAX_MCP_CALLS_VARIABLE = "AI_AGENT_MAX_MCP_CALLS_PER_MESSAGE"

# HTTP statuses that will not get better by asking again.
_NOT_WORTH_RETRYING = (400, 401, 403, 404)

PHASE_ACTIVITIES = {
    1: "understanding your request",
    2: "planning the steps",
    3: "checking that the plan is safe",
    4: "working on a step",
    5: "using a tool",
    6: "cleaning a tool result",
    7: "writing the answer",
    8: "polishing the answer",
    9: "reading your answer",
    20: "working out the movement",
    99: "writing a question for you",
}

# category -> (what happened, why)
_EXPLANATIONS = {
    "connection": ("I could not reach the language model service",
                   "the network or the service is down"),
    "timeout": ("the language model service took too long to answer",
                "it may be overloaded"),
    "rate_limit": ("the language model service refused more requests for now",
                   "the request limit or quota was reached"),
    "auth": ("the language model service did not accept my credentials",
             "the API key is missing, wrong or not allowed to use that model"),
    "not_found": ("the language model service does not know the model I asked for",
                  "the model name or the service address is wrong or the model was retired"),
    "bad_request": ("the language model service rejected my request",
                    "the request or the answer format I asked for was not accepted"),
    "bad_answer": ("the language model answered in a format I could not read",
                   "the answer was not the JSON I asked for"),
    "reported_error": ("one of my steps reported an error and kept failing",
                       "the model marked its own answer as an error"),
    "unknown": ("something unexpected went wrong on my side",
                "the cause was not recognised"),
}


def max_attempts() -> int:
    """How many times something is tried in total (the first try included)."""
    try:
        return max(1, int(os.environ.get(MAX_ATTEMPTS_VARIABLE, DEFAULT_MAX_ATTEMPTS)))
    except ValueError:
        return DEFAULT_MAX_ATTEMPTS


def max_mcp_calls() -> int:
    """
    How many MCP tool actions one message may run; 0 means no limit. A value that is not a whole number, or is
    negative, falls back to the default with a warning (never to 0: a typing mistake must not remove the limit).
    """
    raw = os.environ.get(MAX_MCP_CALLS_VARIABLE, "").strip()
    if not raw:
        return DEFAULT_MAX_MCP_CALLS
    try:
        value = int(raw)
    except ValueError:
        value = -1
    if value < 0:
        logger.warning("Invalid MCP call limit, using the default", variable=MAX_MCP_CALLS_VARIABLE, default=DEFAULT_MAX_MCP_CALLS)
        return DEFAULT_MAX_MCP_CALLS
    return value


def classify(error: BaseException) -> str:
    """The category of an error, from what it is and, for HTTP errors, its status code."""
    status = getattr(error, "status_code", None)

    if status == 429:
        return "rate_limit"
    if status in (401, 403):
        return "auth"
    if status == 404:
        return "not_found"
    if status == 400:
        return "bad_request"

    name = type(error).__name__
    if "Timeout" in name:
        return "timeout"
    if "Connection" in name or isinstance(error, (ConnectionError, OSError)):
        return "connection"
    if isinstance(error, (ValueError, TypeError, KeyError)):   # includes JSONDecodeError and domain validation
        return "bad_answer"

    return "unknown"


def worth_retrying(error: BaseException) -> bool:
    return getattr(error, "status_code", None) not in _NOT_WORTH_RETRYING


def capacity_problem(error: BaseException) -> bool:
    """The provider is out of capacity or unreachable for now (429, any 5xx, a timeout, no connection): another model may answer."""
    status = getattr(error, "status_code", None)
    if status == 429 or (isinstance(status, int) and status >= 500):
        return True
    return classify(error) in ("timeout", "connection")


def daily_quota_used_up(error: BaseException) -> bool:
    """A 429 that says the quota of the DAY is gone (Google: "requests per day"): waiting seconds cannot help, so go to the next model."""
    text = str(error).lower()
    return getattr(error, "status_code", None) == 429 and ("per day" in text or "perday" in text)


def retry_wait_seconds() -> float:
    try:
        return max(0.0, float(os.environ.get(RETRY_WAIT_VARIABLE, DEFAULT_RETRY_WAIT_SECONDS)))
    except ValueError:
        return DEFAULT_RETRY_WAIT_SECONDS


def wait_before_retry(attempt: int, error: BaseException) -> None:
    """Waits before try number attempt + 1 when the failure was a lack of capacity (never for any other error)."""
    wait = retry_wait_seconds()
    if wait > 0 and capacity_problem(error):
        time.sleep(min(wait * (2 ** (attempt - 1)), wait * 8))


class AgentFailure(Exception):
    """A phase could not be completed. Carries what the user is told."""

    def __init__(self, category: str, phase_id: Optional[int] = None, cause: Optional[BaseException] = None) -> None:
        self.category = category if category in _EXPLANATIONS else "unknown"
        self.phase_id = phase_id
        self.cause = cause
        super().__init__(f"{self.category} while {PHASE_ACTIVITIES.get(phase_id, 'working') if phase_id is not None else 'working'}"
                         + (f": {type(cause).__name__}" if cause else ""))

    def apology(self) -> str:
        return apology(self.category, self.phase_id)

    def explanation(self) -> str:
        """Short text for the failed step: what happened and why."""
        what, why = _EXPLANATIONS[self.category]
        return f"{what[0].upper()}{what[1:]} ({why})."


def apology(category: str, phase_id: Optional[int] = None) -> str:
    what, why = _EXPLANATIONS.get(category, _EXPLANATIONS["unknown"])
    when = f" while {PHASE_ACTIVITIES[phase_id]}" if phase_id in PHASE_ACTIVITIES else ""
    return f"Sorry, I could not finish your request. What happened: {what}{when}. Why: {why}. Please try again in a moment."


def apology_for_unexpected(error: BaseException) -> str:
    """The apology for any error: the specific one for an AgentFailure, a general one otherwise."""
    return error.apology() if isinstance(error, AgentFailure) else apology("unknown")


UNKNOWN_SESSION_APOLOGY = ("Sorry, I could not find this conversation. What happened: the session does not exist "
                           "or was already ended. Why: it was never started or it expired. Please start a new session.")
