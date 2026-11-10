"""HTTP_ADDR: the listen address, in the format of dynamics_microservice."""
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from infrastructure.inbound.http.address import parse_http_addr


@pytest.mark.parametrize("value, expected", [
    ("", ("0.0.0.0", 7998)),
    ("   ", ("0.0.0.0", 7998)),
    (":30003", ("0.0.0.0", 30003)),
    ("127.0.0.1:8080", ("127.0.0.1", 8080)),
    ("0.0.0.0:7998", ("0.0.0.0", 7998)),
    ("7998", ("0.0.0.0", 7998)),
    ("[::1]:9000", ("::1", 9000)),
    (" :31003 ", ("0.0.0.0", 31003)),
])
def test_parse_http_addr(value, expected):
    assert parse_http_addr(value) == expected


@pytest.mark.parametrize("value", [":abc", "host:", ":0", ":70000", "localhost"])
def test_parse_http_addr_refuses_a_wrong_address(value):
    with pytest.raises(ValueError):
        parse_http_addr(value)
