"""Tenant-scoped policy store for SentraAura.

Policy rules are a security boundary: a rule decides whether content may be
published.  The store therefore partitions every rule by the tenant that owns
the channel it belongs to, and every accessor takes the tenant explicitly.

The previous implementation was a bare ``dict[channel_id, list[rule]]``:
``get("chan-1")`` returned the rules regardless of who asked, so one tenant
could read -- and, via the write path, replace -- another tenant's governance
decisions.  Making the tenant a required argument means a caller cannot reach
a cross-tenant rule even by accident, and a channel id from another tenant is
indistinguishable from a channel that does not exist.

State remains in-process; durable persistence is tracked separately.
"""
from __future__ import annotations

from policy_engine.models import PolicyRule

#: Separator used to build the composite storage key.  Channel ids are opaque
#: URL-safe tokens, so a NUL keeps the components unambiguous.
_SEP = "\x00"


class PolicyStore:
    """Policy store partitioned by ``(tenant_id, channel_id)``."""

    def __init__(self) -> None:
        self._policies: dict[str, list[PolicyRule]] = {}

    @staticmethod
    def _key(tenant_id: str, channel_id: str) -> str:
        return f"{tenant_id}{_SEP}{channel_id}"

    def add(self, tenant_id: str, channel_id: str, rule: PolicyRule) -> None:
        """Add a rule for ``channel_id`` owned by ``tenant_id``."""
        self._policies.setdefault(self._key(tenant_id, channel_id), []).append(rule)

    def get(self, tenant_id: str, channel_id: str) -> list[PolicyRule]:
        """Return the rules for a channel **owned by this tenant**.

        A channel belonging to a different tenant yields an empty list -- the
        caller learns nothing about whether it exists.
        """
        return self._policies.get(self._key(tenant_id, channel_id), [])

    def clear(self, tenant_id: str, channel_id: str) -> None:
        """Drop the rules for one channel owned by this tenant."""
        self._policies[self._key(tenant_id, channel_id)] = []

    def list_for_tenant(self, tenant_id: str) -> dict[str, list[PolicyRule]]:
        """Return every rule this tenant owns, keyed by bare channel id.

        Only the caller's own partition is ever returned; other tenants' rules
        are not visible.
        """
        prefix = f"{tenant_id}{_SEP}"
        return {
            key[len(prefix):]: rules
            for key, rules in self._policies.items()
            if key.startswith(prefix)
        }
