"""Regression tests for DecisionLogRepository.override.

Guards a latent ``NameError``: ``repositories.py`` called ``datetime.utcnow()``
without importing ``datetime``. The module imported cleanly and ``ruff`` F821
was the only signal, so the defect only surfaced when the override path was
actually exercised (operator override of a governance decision).
"""
from __future__ import annotations

from typing import Any

from control_plane_api import repositories


class _FakeLog:
    """Minimal stand-in for a DecisionLog row."""

    override_status: str | None = None
    override_by: str | None = None
    override_at: Any = None


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False

    def commit(self) -> None:
        self.committed = True

    def refresh(self, obj: Any) -> None:  # pragma: no cover - trivial
        return None


def _repo_with(log: _FakeLog) -> tuple[repositories.DecisionLogRepository, _FakeSession]:
    repo = repositories.DecisionLogRepository.__new__(repositories.DecisionLogRepository)
    session = _FakeSession()
    repo.db = session  # type: ignore[assignment]
    repo.get = lambda decision_id: log  # type: ignore[method-assign]
    return repo, session


def test_override_sets_timestamp_without_nameerror() -> None:
    repo, session = _repo_with(_FakeLog())

    result = repo.override("decision-1", "ops@example.com", "rejected")

    assert result is not None
    assert result.override_status == "rejected"
    assert result.override_by == "ops@example.com"
    assert result.override_at is not None
    assert session.committed is True


def test_override_returns_none_for_unknown_decision() -> None:
    repo = repositories.DecisionLogRepository.__new__(repositories.DecisionLogRepository)
    repo.db = _FakeSession()  # type: ignore[assignment]
    repo.get = lambda decision_id: None  # type: ignore[method-assign]

    assert repo.override("missing", "ops@example.com", "rejected") is None
