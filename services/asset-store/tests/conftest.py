"""Shared fixtures for the asset-store test suite.

These tests exercise ``AssetStoreService``, which persists through the SQLAlchemy
ORM. Nothing previously provisioned the schema: the suite therefore failed with
``psycopg2.errors.UndefinedTable: relation "assets" does not exist`` on a clean
database, and CI never provisioned one at all, so the leg could not pass on any
commit. The fixtures below make the suite self-sufficient - it creates the
schema it needs and isolates each test - instead of silently depending on a
pre-migrated external database.
"""
from __future__ import annotations

import pytest

# Importing the ORM module registers the tables on ``Base.metadata``;
# ``init_db()`` would otherwise create nothing.
from asset_store.db import models  # noqa: F401
from asset_store.db.session import Base, get_engine, init_db


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    """Create the full schema once per test session."""
    init_db()
    yield


@pytest.fixture(autouse=True)
def _clean_tables() -> None:
    """Truncate every ORM table between tests.

    Several tests assert on ``list_assets(...)[0]`` for a shared channel id, so
    leftover rows from a previous test would make them order-dependent.
    """
    yield
    engine = get_engine()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
