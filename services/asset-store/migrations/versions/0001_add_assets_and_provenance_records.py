"""Add assets and provenance_records tables.

Revision ID: 0001
Revises: 
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'assets',
        sa.Column('asset_id', sa.String(length=32), nullable=False),
        sa.Column('channel_id', sa.String(length=32), nullable=False),
        sa.Column('tenant_id', sa.String(length=32), nullable=False),
        sa.Column('asset_type', sa.String(length=64), nullable=False),
        sa.Column('filename', sa.String(length=512), nullable=False),
        sa.Column('content_type', sa.String(length=128), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('storage_path', sa.String(length=1024), nullable=False),
        sa.Column('storage_provider', sa.String(length=64), nullable=False),
        sa.Column('checksum', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('asset_id'),
        sa.Index('ix_assets_channel_id', 'channel_id'),
        sa.Index('ix_assets_tenant_id', 'tenant_id'),
        sa.Index('ix_assets_asset_type', 'asset_type'),
        sa.Index('ix_assets_status', 'status'),
        sa.Index('ix_assets_is_deleted', 'is_deleted')
    )
    op.create_table(
        'provenance_records',
        sa.Column('record_id', sa.String(length=32), nullable=False),
        sa.Column('asset_id', sa.String(length=32), nullable=False),
        sa.Column('channel_id', sa.String(length=32), nullable=False),
        sa.Column('tenant_id', sa.String(length=32), nullable=False),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('agent_id', sa.String(length=64), nullable=False),
        sa.Column('source_asset_ids', sa.JSON(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.asset_id']),
        sa.PrimaryKeyConstraint('record_id'),
        sa.Index('ix_provenance_records_asset_id', 'asset_id'),
        sa.Index('ix_provenance_records_channel_id', 'channel_id'),
        sa.Index('ix_provenance_records_tenant_id', 'tenant_id')
    )


def downgrade() -> None:
    op.drop_table('provenance_records')
    op.drop_table('assets')
