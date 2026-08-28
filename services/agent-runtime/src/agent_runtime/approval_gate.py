"""Approval gate for ESCALATE-tier tool invocations (Arch. §3 HITL, §16.2 tool manifest).

Control-plane Backend docs reference services/approval_service.py for content
risk queues; that module is not present in-tree. This gate is the agent-runtime
enforcement point for tool-level ApprovalRequiredError: scoped, expiring,
single-use grants that must be issued through grant_approval() before
invoke_tool may proceed on an ESCALATE+requires_approval rule.

When control-plane approval_service is implemented, this store can be backed by
its API without changing agent call sites.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApprovalScope:
    agent_id: str
    tool_name: str
    action: str = "execute"
    # Optional tighter binding (e.g. content hash / task id). Empty = tool-level only.
    scope_key: str = ""

    def fingerprint(self) -> str:
        raw = f"{self.agent_id}|{self.tool_name}|{self.action}|{self.scope_key}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]


@dataclass
class PendingApproval:
    approval_id: str
    scope: ApprovalScope
    created_at: float
    expires_at: float
    context: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending | granted | consumed | expired | rejected
    approved_by: str | None = None
    granted_at: float | None = None


# Roles/actors allowed to grant approvals (extend via config in production)
AUTHORIZED_APPROVERS: frozenset[str] = frozenset({
    "control-plane",
    "human-ops",
    "security-officer",
    "channel-owner",
    "system-test",  # explicit test actor only
})


class ApprovalGate:
    """In-process approval store with scoped, expiring, single-use grants."""

    def __init__(self, default_ttl_seconds: float = 3600.0) -> None:
        self.default_ttl_seconds = default_ttl_seconds
        self._lock = Lock()
        self._records: dict[str, PendingApproval] = {}
        # fingerprint -> approval_id for active granted (not yet consumed)
        self._granted_by_fp: dict[str, str] = {}

    def request(
        self,
        scope: ApprovalScope,
        *,
        context: dict[str, Any] | None = None,
        ttl_seconds: float | None = None,
    ) -> PendingApproval:
        ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        now = time.time()
        rec = PendingApproval(
            approval_id=secrets.token_hex(12),
            scope=scope,
            created_at=now,
            expires_at=now + ttl,
            context=dict(context or {}),
            status="pending",
        )
        with self._lock:
            self._records[rec.approval_id] = rec
        logger.info(
            "Approval requested id=%s agent=%s tool=%s scope_key=%s",
            rec.approval_id,
            scope.agent_id,
            scope.tool_name,
            scope.scope_key,
        )
        return rec

    def grant(
        self,
        approval_id: str,
        *,
        approved_by: str,
    ) -> PendingApproval:
        """Human/authorized actor grants a pending approval."""
        if not approved_by or not str(approved_by).strip():
            raise ValueError("approved_by is required")
        actor = str(approved_by).strip()
        authorized = (
            actor in AUTHORIZED_APPROVERS
            or actor.startswith("approver:")
            or actor.endswith("@sentra.test")
            or actor.endswith("@sentra")
            or actor.endswith("@sentra.local")
        )
        if not authorized:
            raise PermissionError(
                f"actor {actor!r} is not authorized to grant approvals; "
                f"allowed={sorted(AUTHORIZED_APPROVERS)}, *@sentra[.test|.local], or 'approver:<id>'"
            )
        with self._lock:
            rec = self._records.get(approval_id)
            if rec is None:
                raise KeyError(f"Unknown approval_id: {approval_id}")
            if rec.status != "pending":
                raise ValueError(f"Approval {approval_id} is not pending (status={rec.status})")
            if time.time() > rec.expires_at:
                rec.status = "expired"
                raise ValueError(f"Approval {approval_id} expired")
            rec.status = "granted"
            rec.approved_by = approved_by
            rec.granted_at = time.time()
            self._granted_by_fp[rec.scope.fingerprint()] = approval_id
        logger.info(
            "Approval GRANTED id=%s by=%s agent=%s tool=%s",
            approval_id,
            approved_by,
            rec.scope.agent_id,
            rec.scope.tool_name,
        )
        return rec

    def reject(self, approval_id: str, *, rejected_by: str) -> PendingApproval:
        with self._lock:
            rec = self._records.get(approval_id)
            if rec is None:
                raise KeyError(f"Unknown approval_id: {approval_id}")
            rec.status = "rejected"
            rec.approved_by = rejected_by
        return rec

    def has_grant(self, scope: ApprovalScope) -> bool:
        """True if a non-expired, granted (not yet consumed) approval matches scope."""
        with self._lock:
            return self._lookup_granted_unlocked(scope) is not None

    def consume_grant(self, scope: ApprovalScope) -> PendingApproval | None:
        """Atomically consume a matching grant so it cannot authorize a second call."""
        with self._lock:
            rec = self._lookup_granted_unlocked(scope)
            if rec is None:
                return None
            rec.status = "consumed"
            self._granted_by_fp.pop(scope.fingerprint(), None)
            logger.info(
                "Approval CONSUMED id=%s agent=%s tool=%s",
                rec.approval_id,
                scope.agent_id,
                scope.tool_name,
            )
            return rec

    def get(self, approval_id: str) -> PendingApproval | None:
        with self._lock:
            return self._records.get(approval_id)

    def _lookup_granted_unlocked(self, scope: ApprovalScope) -> PendingApproval | None:
        fp = scope.fingerprint()
        aid = self._granted_by_fp.get(fp)
        if not aid:
            return None
        rec = self._records.get(aid)
        if rec is None or rec.status != "granted":
            self._granted_by_fp.pop(fp, None)
            return None
        if time.time() > rec.expires_at:
            rec.status = "expired"
            self._granted_by_fp.pop(fp, None)
            return None
        # Exact scope match (fingerprint already encodes fields)
        if (
            rec.scope.agent_id != scope.agent_id
            or rec.scope.tool_name != scope.tool_name
            or rec.scope.action != scope.action
            or rec.scope.scope_key != scope.scope_key
        ):
            return None
        return rec


# Process-wide default gate (agents may inject their own for isolation in tests)
_default_gate = ApprovalGate()


def get_default_approval_gate() -> ApprovalGate:
    return _default_gate
