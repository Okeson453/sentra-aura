"""Add bounded-attempt lease fields for clipping worker claims."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260323_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clip_jobs", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("clip_jobs", sa.Column("claimed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("clip_jobs", "claimed_at")
    op.drop_column("clip_jobs", "attempt_count")
