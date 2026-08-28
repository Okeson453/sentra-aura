"""In-memory policy store for SentraAura."""
from __future__ import annotations

from typing import Any

from policy_engine.models import PolicyRule, AutonomyLevel


class PolicyStore:
    """Simple in-memory policy store."""

    def __init__(self) -> None:
        self._policies: dict[str, list[PolicyRule]] = {}

    def add(self, channel_id: str, rule: PolicyRule) -> None:
        if channel_id not in self._policies:
            self._policies[channel_id] = []
        self._policies[channel_id].append(rule)

    def get(self, channel_id: str) -> list[PolicyRule]:
        return self._policies.get(channel_id, [])

    def clear(self, channel_id: str) -> None:
        self._policies[channel_id] = []

    def list_all(self) -> dict[str, list[PolicyRule]]:
        return self._policies
