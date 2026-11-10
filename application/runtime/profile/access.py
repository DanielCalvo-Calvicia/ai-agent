# ===============================================
#  PROFILE ACCESS
#  Which profile a request may run: the one it names (`default` when it names none) if its token is right. The token is a check
#  against a mistake, not access control (Q08-8): the profile holds the SHA-256 of it, the client sends the token, the hashes are
#  compared in constant time. An unknown profile, a disabled one and a wrong token are the same refusal for the client; the reason
#  is only for the log, and never holds the token.
# ===============================================

import hashlib
import hmac
from dataclasses import dataclass
from typing import Optional

from application.engine.assemble import DEFAULT_PROFILE, Agent, AssembledProfile

NO_HASH = "0" * 64        # what an unknown profile is compared with, so refusing it takes as long as refusing a wrong token

REASON_UNKNOWN = "unknown_or_disabled_profile"
REASON_NO_TOKEN = "no_token"
REASON_WRONG_TOKEN = "wrong_token"


@dataclass(frozen=True)
class Access:
    profile: Optional[AssembledProfile]
    reason: str = ""                  # why it was refused: for the log only, never for the client

    @property
    def allowed(self) -> bool:
        return self.profile is not None


def sha256_hex(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def check_access(agent: Optional[Agent], name: Optional[str], token: Optional[str]) -> Access:
    """The profile named (or `default`) when the token is right; `default` needs none."""
    name = name or DEFAULT_PROFILE
    profile = agent.profiles.get(name) if agent is not None else None
    expected = (profile.definition.get("token_sha256") if profile is not None else None) or NO_HASH
    given = sha256_hex(token) if token else NO_HASH
    matches = hmac.compare_digest(given, expected)

    if profile is None:
        return Access(None, REASON_UNKNOWN)
    if name == DEFAULT_PROFILE:
        return Access(profile)
    if not token:
        return Access(None, REASON_NO_TOKEN)
    return Access(profile) if matches and expected != NO_HASH else Access(None, REASON_WRONG_TOKEN)
