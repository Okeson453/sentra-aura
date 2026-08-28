"""Create agent_checkpoints table (real schema baseline).

Revision ID: 001_baseline
Revises:
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("agent_id", sa.String(128), nullable=False, index=True),
        sa.Column("checkpoint_id", sa.String(64), nullable=False, unique=True),
        sa.Column("phase", sa.String(64), nullable=False, server_default="idle"),
        sa.Column("cost_accrued_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tokens_consumed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("agent_checkpoints")
