"""Add render_jobs, transcode_jobs, and render_templates tables.

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
        'render_templates',
        sa.Column('template_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.String(length=512), nullable=False),
        sa.Column('compatible_formats', sa.JSON(), nullable=False),
        sa.Column('default_settings', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('template_id'),
        sa.Index('ix_render_templates_template_id', 'template_id')
    )
    op.create_table(
        'render_jobs',
        sa.Column('job_id', sa.String(length=32), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('channel_id', sa.String(length=32), nullable=False),
        sa.Column('tenant_id', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('progress_percent', sa.Integer(), nullable=False),
        sa.Column('output_url', sa.String(length=1024), nullable=False),
        sa.Column('output_format', sa.String(length=16), nullable=False),
        sa.Column('resolution', sa.String(length=16), nullable=False),
        sa.Column('frame_rate', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('render_plan', sa.JSON(), nullable=False),
        sa.Column('timeline_clips', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.String(length=64), nullable=True),
        sa.Column('callback_url', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['render_templates.template_id']),
        sa.PrimaryKeyConstraint('job_id'),
        sa.Index('ix_render_jobs_channel_id', 'channel_id'),
        sa.Index('ix_render_jobs_tenant_id', 'tenant_id'),
        sa.Index('ix_render_jobs_status', 'status'),
        sa.Index('ix_render_jobs_project_id', 'project_id'),
        sa.Index('ix_render_jobs_is_deleted', 'is_deleted')
    )
    op.create_table(
        'transcode_jobs',
        sa.Column('job_id', sa.String(length=32), nullable=False),
        sa.Column('source_asset_id', sa.String(length=64), nullable=False),
        sa.Column('channel_id', sa.String(length=32), nullable=False),
        sa.Column('tenant_id', sa.String(length=32), nullable=False),
        sa.Column('target_format', sa.String(length=16), nullable=False),
        sa.Column('target_resolution', sa.String(length=16), nullable=False),
        sa.Column('target_codec', sa.String(length=16), nullable=False),
        sa.Column('bitrate_kbps', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('progress_percent', sa.Integer(), nullable=False),
        sa.Column('output_url', sa.String(length=1024), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('job_id'),
        sa.Index('ix_transcode_jobs_source_asset_id', 'source_asset_id'),
        sa.Index('ix_transcode_jobs_channel_id', 'channel_id'),
        sa.Index('ix_transcode_jobs_tenant_id', 'tenant_id'),
        sa.Index('ix_transcode_jobs_status', 'status'),
        sa.Index('ix_transcode_jobs_is_deleted', 'is_deleted')
    )


def downgrade() -> None:
    op.drop_table('transcode_jobs')
    op.drop_table('render_jobs')
    op.drop_table('render_templates')
