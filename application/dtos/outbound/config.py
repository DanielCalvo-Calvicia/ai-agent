# The classes the outbound adapters exchange with the application. They are the domain's own classes, not copies:
# an adapter imports them from here and never from `domain/` (tests/test_clean_architecture.py).

from domain.errors.config_error import ConfigError
from domain.value_objects.config.loaded import Loaded

__all__ = ["ConfigError", "Loaded"]
