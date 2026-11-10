"""The address the HTTP server listens on, read from HTTP_ADDR (the name and the format of dynamics_microservice)."""
from typing import Tuple

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 7998


def parse_http_addr(value: str) -> Tuple[str, int]:
    """
    `HTTP_ADDR` as `host:port` or `:port` (no host = every interface, as in Go), or a bare port.
    Empty = `0.0.0.0:7998`. Raises ValueError for a port that is not a number from 1 to 65535, so a wrong
    setting stops the start instead of binding somewhere unexpected.
    """
    text = (value or "").strip()
    if not text:
        return DEFAULT_HOST, DEFAULT_PORT

    host, separator, port_text = text.rpartition(":")
    if not separator:
        host, port_text = "", text          # a bare port: "7998"
    host = host.strip().strip("[]") or DEFAULT_HOST

    try:
        port = int(port_text)
    except ValueError:
        raise ValueError(f"HTTP_ADDR must be host:port or :port, not {text!r}") from None
    if not 1 <= port <= 65535:
        raise ValueError(f"HTTP_ADDR port must be between 1 and 65535, not {port}")
    return host, port
