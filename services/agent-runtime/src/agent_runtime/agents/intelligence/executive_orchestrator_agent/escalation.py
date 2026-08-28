"""Escalation evaluation for Executive Orchestrator (Arch. §4.2).

Conditions (must evaluate against real orchestrator/workflow state structures):
  1. Workflow stuck > 2h (no progress)
  2. Resource exhaustion > 80% sustained for 1h
  3. Budget overrun > 10%
  4. >= 5 consecutive failures
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


STUCK_HOURS = 2.0
RESOURCE_THRESHOLD = 0.80
RESOURCE_WINDOW_HOURS = 1.0
BUDGET_OVERRUN_RATIO = 0.10
CONSECUTIVE_FAILURES = 5


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        # unix seconds
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        try:
            # support Z
            v = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(v)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def evaluate_escalations(
    *,
    workflow_state: dict[str, Any] | None,
    resource_metrics: dict[str, Any] | None,
    budget_metrics: dict[str, Any] | None,
    failure_history: list[dict[str, Any]] | None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return list of triggered escalation records from structured state."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    escalations: list[dict[str, Any]] = []

    # 1) Workflow stuck > 2h
    wf = workflow_state or {}
    active = wf.get("active_workflows") or wf.get("workflows") or []
    if isinstance(active, list):
        for w in active:
            if not isinstance(w, dict):
                continue
            status = str(w.get("status") or "running").lower()
            if status in ("completed", "cancelled", "failed", "succeeded"):
                continue
            progress_at = _parse_ts(w.get("last_progress_at") or w.get("updated_at") or w.get("started_at"))
            if progress_at is None:
                continue
            hours = (now - progress_at).total_seconds() / 3600.0
            if hours > STUCK_HOURS:
                escalations.append({
                    "condition": "workflow_stuck",
                    "severity": "high",
                    "workflow_id": w.get("id") or w.get("workflow_id"),
                    "hours_since_progress": round(hours, 2),
                    "threshold_hours": STUCK_HOURS,
                    "message": f"Workflow stuck for {hours:.1f}h without progress (threshold {STUCK_HOURS}h)",
                })

    # 2) Resource exhaustion > 80% for 1h
    rm = resource_metrics or {}
    cpu = float(rm.get("cpu_utilization") or rm.get("cpu") or 0.0)
    mem = float(rm.get("memory_utilization") or rm.get("memory") or 0.0)
    # Accept 0–1 or 0–100
    if cpu > 1.0:
        cpu = cpu / 100.0
    if mem > 1.0:
        mem = mem / 100.0
    window = float(rm.get("exhaustion_window_hours") or rm.get("window_hours") or 0.0)
    peak = max(cpu, mem)
    if peak > RESOURCE_THRESHOLD and window >= RESOURCE_WINDOW_HOURS:
        escalations.append({
            "condition": "resource_exhaustion",
            "severity": "high",
            "cpu_utilization": cpu,
            "memory_utilization": mem,
            "window_hours": window,
            "threshold": RESOURCE_THRESHOLD,
            "message": (
                f"Resource exhaustion {peak:.0%} for {window:.1f}h "
                f"(threshold {RESOURCE_THRESHOLD:.0%} / {RESOURCE_WINDOW_HOURS}h)"
            ),
        })

    # 3) Budget overrun > 10%
    bm = budget_metrics or {}
    allocated = float(bm.get("allocated_usd") or bm.get("budget_usd") or 0.0)
    spent = float(bm.get("spent_usd") or bm.get("actual_usd") or 0.0)
    if allocated > 0:
        overrun = (spent - allocated) / allocated
        if overrun > BUDGET_OVERRUN_RATIO:
            escalations.append({
                "condition": "budget_overrun",
                "severity": "medium",
                "allocated_usd": allocated,
                "spent_usd": spent,
                "overrun_ratio": round(overrun, 4),
                "threshold": BUDGET_OVERRUN_RATIO,
                "message": f"Budget overrun {overrun:.1%} (threshold {BUDGET_OVERRUN_RATIO:.0%})",
            })

    # 4) >= 5 consecutive failures (from end of history)
    history = failure_history or []
    consecutive = 0
    for entry in reversed(history):
        if not isinstance(entry, dict):
            break
        # success breaks the streak
        if entry.get("success") is True or str(entry.get("status") or "").lower() in ("ok", "success"):
            break
        consecutive += 1
    if consecutive >= CONSECUTIVE_FAILURES:
        escalations.append({
            "condition": "consecutive_failures",
            "severity": "high",
            "count": consecutive,
            "threshold": CONSECUTIVE_FAILURES,
            "message": f"{consecutive} consecutive failures (threshold {CONSECUTIVE_FAILURES})",
        })

    return escalations
