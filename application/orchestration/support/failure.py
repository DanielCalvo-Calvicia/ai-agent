# ===============================================
#  FAILURE
#  What went wrong during a message, and the apology that tells the user
#  what happened and why. The apology is a template (not an LLM call),
#  so it still works when the LLM is the thing that failed.
#  It never includes raw error text: that can hold request details.
# ===============================================

import os
from typing import Optional

# One setting for every "try again" of the agent: LLM calls, MCP tool calls, status `retry`.
DEFAULT_MAX_ATTEMPTS = 3
MAX_ATTEMPTS_VARIABLE = "AI_AGENT_MAX_ATTEMPTS"

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
