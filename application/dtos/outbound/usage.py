# The classes the outbound adapters exchange with the application. They are the domain's own classes, not copies:
# an adapter imports them from here and never from `domain/` (tests/test_clean_architecture.py).

from domain.value_objects.usage.call_details import CallDetails
from domain.value_objects.usage.request_record import RequestRecord

__all__ = ["CallDetails", "RequestRecord"]
