"""create recommendation_events table

Revision ID: 001
Revises:
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'recommendation_events',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('snapshot_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('connector', sa.String(50), nullable=False),
        sa.Column('query_params', JSONB, nullable=True),
        sa.Column('input_load_ids', JSONB, nullable=False),
        sa.Column('output_top3', JSONB, nullable=False),
        sa.Column('full_payload', JSONB, nullable=False),
        sa.Column('loads_analyzed', sa.Integer(), nullable=False, default=0),
        sa.Column('loads_feasible', sa.Integer(), nullable=False, default=0),
        sa.Column('warnings', JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_table('recommendation_events')
