"""Audit log builder for SentraAura.

Immutable, append-only audit trail per Architecture §16.3.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


class AuditLogBuilder:
    """Builder for standardized audit log entries."""

    def __init__(self) -> None:
        self._entry: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def actor(self, user_id: str | None = None, agent_type: str | None = None) -> "AuditLogBuilder":
        if user_id:
            self._entry["user_id"] = user_id
        if agent_type:
            self._entry["agent_type"] = agent_type
        return self

    def action(self, action: str, resource_type: str, resource_id: str) -> "AuditLogBuilder":
        self._entry["action"] = action
        self._entry["resource_type"] = resource_type
        self._entry["resource_id"] = resource_id
        return self

    def details(self, details: dict[str, Any]) -> "AuditLogBuilder":
        self._entry["details"] = details
        return self

    def channel(self, channel_id: str, tenant_id: str | None = None) -> "AuditLogBuilder":
        self._entry["channel_id"] = channel_id
        if tenant_id:
            self._entry["tenant_id"] = tenant_id
        return self

    def client_info(self, ip_address: str | None = None, user_agent: str | None = None) -> "AuditLogBuilder":
        if ip_address:
            self._entry["ip_address"] = ip_address
        if user_agent:
            self._entry["user_agent"] = user_agent
        return self

    def success(self, success: bool, error_message: str | None = None) -> "AuditLogBuilder":
        self._entry["success"] = success
        if error_message:
            self._entry["error_message"] = error_message
        return self

    def build(self) -> dict[str, Any]:
        required = ["action", "resource_type", "resource_id", "success"]
        for key in required:
            if key not in self._entry:
                raise ValueError(f"Audit log missing required field: {key}")
        return self._entry.copy()
