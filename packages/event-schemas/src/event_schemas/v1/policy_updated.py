"""Pydantic model for policy.updated event."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PolicyUpdated(BaseModel):
    event_id: str
    event_type: str = "policy.updated"
    timestamp: datetime
    channel_id: str
    policy_id: str
    previous_version: str | None = None
    new_version: str | None = None
    change_reason: str | None = None
    approved_by: str | None = None
    weights_delta: dict[str, Any] | None = None
