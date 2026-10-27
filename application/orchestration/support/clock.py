# ===============================================
#  CLOCK
#  The current date and time, as the phases read it.
# ===============================================

from datetime import datetime


def now_text() -> str:
    """For example: Monday, 2026-09-21, 14:03 (UTC+02:00)."""
    now = datetime.now().astimezone()
    offset = now.strftime("%z")
    return f"{now.strftime('%A, %Y-%m-%d, %H:%M')} (UTC{offset[:3]}:{offset[3:]})"
