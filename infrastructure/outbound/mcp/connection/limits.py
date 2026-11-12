"""How long the MCP client waits (seconds). The time one message may wait for all its tools is the application's budget
(`application/ports/outbound/tool_wait_budget.py`), not a number here."""

import math
import os

from shared_logging import get_logger

logger = get_logger(__name__)

# Seconds to wait for one MCP server to list its tools before giving up on it.
LIST_TIMEOUT_SECONDS = 10

# A listing that failed is not tried again for this long, so a server that is down costs one LIST_TIMEOUT_SECONDS wait
# per minute (a successful listing is kept for the life of the process).
FAILED_LISTING_TTL_SECONDS = 60

# Seconds one tool call may take (connect, initialize and the call). A slow query makes the server wait up to
# 20 s (dynamics_microservice MCP_JOB_WAIT) before it answers `running`, so this stays above that.
CALL_TIMEOUT_VARIABLE = "AI_AGENT_MCP_CALL_TIMEOUT_SECONDS"
DEFAULT_CALL_TIMEOUT_SECONDS = 30


def call_timeout_seconds() -> float:
    """The limit of one tool call: the variable, or the default when it is not a positive number."""
    raw = os.environ.get(CALL_TIMEOUT_VARIABLE, "").strip()
    if not raw:
        return DEFAULT_CALL_TIMEOUT_SECONDS
    try:
        value = float(raw)
        if value > 0 and math.isfinite(value):
            return value
    except ValueError:
        pass
    logger.warning("Invalid MCP call timeout, using the default", variable=CALL_TIMEOUT_VARIABLE, default=DEFAULT_CALL_TIMEOUT_SECONDS)
    return DEFAULT_CALL_TIMEOUT_SECONDS
