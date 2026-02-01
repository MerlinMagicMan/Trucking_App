"""multi-tenant tables

Revision ID: 003
Revises: 002
Create Date: 2026-01-31 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Organizations
    op.create_table(
        'organizations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )

    # Trucks
    op.create_table(
        'trucks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('equipment_type', sa.String(50), nullable=False, server_default='reefer'),
        sa.Column('home_base_city', sa.String(100), nullable=True),
        sa.Column('home_base_state', sa.String(2), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )
    op.create_index('ix_trucks_org_id', 'trucks', ['org_id'])

    # Routes (persisted load templates)
    op.create_table(
        'routes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('source', sa.String(50), nullable=False, server_default='user_uploaded'),
        sa.Column('external_id', sa.String(255), nullable=True),
        sa.Column('pickup_city', sa.String(100), nullable=False),
        sa.Column('pickup_state', sa.String(10), nullable=False),
        sa.Column('delivery_city', sa.String(100), nullable=False),
        sa.Column('delivery_state', sa.String(10), nullable=False),
        sa.Column('rate_total', sa.Float, nullable=False),
        sa.Column('miles', sa.Float, nullable=True),
        sa.Column('posted_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )
    op.create_index('ix_routes_org_id', 'routes', ['org_id'])

    # Add org_id to existing event tables
    op.add_column('recommendation_events', sa.Column('org_id', UUID(as_uuid=True), nullable=True))
    op.create_index('ix_recommendation_events_org_id', 'recommendation_events', ['org_id'])

    op.add_column('plan_generation_events', sa.Column('org_id', UUID(as_uuid=True), nullable=True))
    op.create_index('ix_plan_generation_events_org_id', 'plan_generation_events', ['org_id'])

    op.add_column('decision_events', sa.Column('org_id', UUID(as_uuid=True), nullable=True))
    op.create_index('ix_decision_events_org_id', 'decision_events', ['org_id'])


def downgrade() -> None:
    op.drop_index('ix_decision_events_org_id', 'decision_events')
    op.drop_column('decision_events', 'org_id')
    op.drop_index('ix_plan_generation_events_org_id', 'plan_generation_events')
    op.drop_column('plan_generation_events', 'org_id')
    op.drop_index('ix_recommendation_events_org_id', 'recommendation_events')
    op.drop_column('recommendation_events', 'org_id')
    op.drop_table('routes')
    op.drop_table('trucks')
    op.drop_table('organizations')
