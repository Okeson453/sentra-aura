"""Add source_path, edl_json, profile_name, metadata_json to render_jobs.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("render_jobs", sa.Column("source_path", sa.String(length=1024), nullable=True))
    op.add_column("render_jobs", sa.Column("edl_json", sa.JSON(), nullable=True))
    op.add_column(
        "render_jobs",
        sa.Column("profile_name", sa.String(length=64), nullable=True, server_default="youtube_1080p"),
    )
    op.add_column("render_jobs", sa.Column("metadata_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("render_jobs", "metadata_json")
    op.drop_column("render_jobs", "profile_name")
    op.drop_column("render_jobs", "edl_json")
    op.drop_column("render_jobs", "source_path")
