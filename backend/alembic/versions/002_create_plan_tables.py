"""create plan tables

Revision ID: 002
Revises: 001
Create Date: 2026-01-29 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. plan_generation_events table (audit log for plan generation requests)
    op.create_table(
        'plan_generation_events',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('snapshot_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('planning_horizon_days', sa.Integer(), nullable=False),
        sa.Column('plans_generated', sa.Integer(), nullable=False),
        sa.Column('full_payload', JSONB, nullable=False, comment='Complete request/response for replay'),
        sa.Column('warnings', JSONB, nullable=True, comment='System warnings'),
        sa.Column('loads_analyzed', sa.Integer(), nullable=True, comment='Total loads analyzed across all connectors'),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True, comment='Time to generate plans in milliseconds'),
    )

    # 2. decision_events table (audit log for when drivers accept/reject plans)
    op.create_table(
        'decision_events',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('plan_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('snapshot_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('decision_type', sa.String(20), nullable=False, comment='accepted, rejected, modified'),
        sa.Column('reason', sa.Text(), nullable=True, comment='Why driver made this decision'),
        sa.Column('full_context', JSONB, nullable=False, comment='Complete plan + decision context'),
    )

    # 3. cost_configuration table (economic constants for economics engine)
    op.create_table(
        'cost_configuration',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('effective_date', sa.DateTime(), nullable=False, index=True),
        sa.Column('fuel_cost_per_mile', sa.Numeric(10, 2), nullable=False, comment='$/mile'),
        sa.Column('toll_cost_per_mile', sa.Numeric(10, 2), nullable=False, comment='$/mile for toll roads'),
        sa.Column('waiting_cost_per_hour', sa.Numeric(10, 2), nullable=False, comment='$/hour for driver time'),
        sa.Column('maintenance_reserve_per_mile', sa.Numeric(10, 2), nullable=False, comment='$/mile for future maintenance'),
        sa.Column('opportunity_cost_per_day', sa.Numeric(10, 2), nullable=False, comment='$/day baseline earnings target'),
        sa.Column('notes', sa.Text(), nullable=True, comment='Rationale for these costs'),
    )

    # Insert default cost configuration
    op.execute("""
        INSERT INTO cost_configuration (
            effective_date,
            fuel_cost_per_mile,
            toll_cost_per_mile,
            waiting_cost_per_hour,
            maintenance_reserve_per_mile,
            opportunity_cost_per_day,
            notes
        ) VALUES (
            NOW(),
            0.85,
            0.12,
            35.00,
            0.15,
            500.00,
            'Default Phase 0 economic constants. Fuel: diesel ~$3.50/gal, 4.1 mpg. Waiting: driver time value. Opportunity: baseline daily target.'
        )
    """)


def downgrade() -> None:
    op.drop_table('cost_configuration')
    op.drop_table('decision_events')
    op.drop_table('plan_generation_events')
