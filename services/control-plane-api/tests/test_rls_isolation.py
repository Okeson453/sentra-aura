#!/usr/bin/env python3
"""Row-level security isolation tests for the Control Plane API.

Proves that tenant-scoped sessions cannot read another tenant's rows.
Matches Security Targets §5.
"""
from __future__ import annotations

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from control_plane_api.db.base import (
    Base,
    set_tenant_context,
    get_tenant_context,
    reset_tenant_context,
)
from control_plane_api.models import Channel


@pytest.fixture
def db_session():
    """Create an in-memory SQLite session for RLS testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestRLSIsolation:
    def test_tenant_a_cannot_see_tenant_b_rows(self, db_session):
        """Tenant A's scoped session must return zero rows for Tenant B."""
        # Create rows for two tenants
        ch_a = Channel(
            id="ch-a", tenant_id="tenant-a", name="Channel A",
            platform="youtube", status="ACTIVE",
        )
        ch_b = Channel(
            id="ch-b", tenant_id="tenant-b", name="Channel B",
            platform="youtube", status="ACTIVE",
        )
        db_session.add_all([ch_a, ch_b])
        db_session.commit()

        # Without tenant context, both rows are visible
        all_rows = db_session.query(Channel).all()
        assert len(all_rows) == 2

        # With tenant-a context, only tenant-a row is visible
        token = set_tenant_context("tenant-a")
        try:
            tenant_a_rows = db_session.query(Channel).all()
            assert len(tenant_a_rows) == 1
            assert tenant_a_rows[0].tenant_id == "tenant-a"
            assert tenant_a_rows[0].name == "Channel A"
        finally:
            reset_tenant_context(token)

        # With tenant-b context, only tenant-b row is visible
        token = set_tenant_context("tenant-b")
        try:
            tenant_b_rows = db_session.query(Channel).all()
            assert len(tenant_b_rows) == 1
            assert tenant_b_rows[0].tenant_id == "tenant-b"
            assert tenant_b_rows[0].name == "Channel B"
        finally:
            reset_tenant_context(token)

    def test_get_by_id_respects_tenant_boundary(self, db_session):
        """A get-by-id query must respect the active tenant context."""
        ch_a = Channel(
            id="ch-a2", tenant_id="tenant-a", name="Channel A2",
            platform="youtube", status="ACTIVE",
        )
        db_session.add(ch_a)
        db_session.commit()

        # Without context, row is found
        assert db_session.query(Channel).filter(Channel.id == "ch-a2").first() is not None

        # With wrong tenant context, row is hidden
        token = set_tenant_context("tenant-b")
        try:
            result = db_session.query(Channel).filter(Channel.id == "ch-a2").first()
            assert result is None
        finally:
            reset_tenant_context(token)

    def test_context_var_isolation_between_threads(self):
        """Tenant context must be stored in a contextvar, not a global."""
        import concurrent.futures

        def worker(tenant_id: str) -> str | None:
            token = set_tenant_context(tenant_id)
            try:
                return get_tenant_context()
            finally:
                reset_tenant_context(token)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(worker, "tenant-a")
            future_b = executor.submit(worker, "tenant-b")
            assert future_a.result() == "tenant-a"
            assert future_b.result() == "tenant-b"

        # Main thread should have no tenant set
        assert get_tenant_context() is None
