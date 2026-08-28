#!/usr/bin/env python3
"""Row-level security policies for tenant isolation.

Revision ID: 20260816_rls_tenant_isolation
Revises:
Create Date: 2026-08-16 12:00:00.000000

Enforces tenant isolation at the database layer for all multi-tenant
tables in the control-plane-api service. Matches Security Targets §5.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260816_rls_tenant_isolation"
down_revision = None
branch_labels = None
depends_on = None

# Tables that have tenant_id and need RLS policies
TENANT_TABLES = [
    "channels",
    "content_plans",
    "scripts",
    "videos",
    "clips",
    "publications",
    "performance_records",
    "experiments",
    "policies",
    "decision_logs",
]


def upgrade() -> None:
    """Enable RLS and create tenant isolation policies."""
    for table in TENANT_TABLES:
        # Enable RLS on the table
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;')
        # Create policy: users can only see rows matching their tenant
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation
            ON {table}
            USING (tenant_id = current_setting('app.current_tenant', true));
            """
        )


def downgrade() -> None:
    """Drop RLS policies and disable RLS."""
    for table in TENANT_TABLES:
        op.execute(f'DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};')
        op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;')
