"""Timezone-aware UTC helpers (P2-04 — replace datetime.utcnow())."""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return current UTC time as ISO-8601 string with Z suffix."""
    return utc_now().isoformat().replace("+00:00", "Z")
