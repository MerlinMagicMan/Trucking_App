"""load_snapshots table

Revision ID: 004
Revises: 003
Create Date: 2026-01-31 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'load_snapshots',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('external_id', sa.String(255), nullable=False),
        sa.Column('raw_payload', JSONB, nullable=False),
        sa.Column('canonical', JSONB, nullable=False),
        sa.Column('ingested_at', sa.DateTime, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('posted_at', sa.DateTime, nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=True),
        sa.Column('equipment', sa.String(50), nullable=True),
        sa.Column('pickup_city', sa.String(100), nullable=True),
        sa.Column('pickup_state', sa.String(10), nullable=True),
        sa.Column('delivery_city', sa.String(100), nullable=True),
        sa.Column('delivery_state', sa.String(10), nullable=True),
        sa.Column('pickup_lat', sa.Float, nullable=True),
        sa.Column('pickup_lng', sa.Float, nullable=True),
        sa.Column('delivery_lat', sa.Float, nullable=True),
        sa.Column('delivery_lng', sa.Float, nullable=True),
        sa.Column('rate_total', sa.Float, nullable=True),
        sa.Column('miles', sa.Float, nullable=True),
        sa.UniqueConstraint('source', 'external_id', name='uq_source_external_id'),
    )
    op.create_index('ix_load_snapshots_org_status', 'load_snapshots', ['org_id', 'status'])
    op.create_index('ix_load_snapshots_pickup_state', 'load_snapshots', ['pickup_state'])
    op.create_index('ix_load_snapshots_delivery_state', 'load_snapshots', ['delivery_state'])


def downgrade() -> None:
    op.drop_table('load_snapshots')
