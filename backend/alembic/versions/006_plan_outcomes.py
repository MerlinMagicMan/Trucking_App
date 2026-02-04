"""006 — Plan prediction snapshots + outcomes (Phase 5, Stratum 4A)

Creates plan_prediction_snapshots (immutable) and plan_outcomes (mutable actuals).
Money stored as NUMERIC(12,2). No floats for money.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    # ---- plan_prediction_snapshots (IMMUTABLE) ----
    op.create_table(
        "plan_prediction_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", sa.String(64), nullable=False),
        sa.Column("plan_generation_event_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        # Top-line predicted numbers (Numeric for money)
        sa.Column("predicted_revenue", sa.Numeric(12, 2), nullable=True),
        sa.Column("predicted_costs", sa.Numeric(12, 2), nullable=True),
        sa.Column("predicted_net_profit", sa.Numeric(12, 2), nullable=True),
        sa.Column("predicted_profit_per_day", sa.Numeric(12, 2), nullable=True),
        sa.Column("predicted_miles_total", sa.Integer(), nullable=True),
        sa.Column("predicted_miles_deadhead", sa.Integer(), nullable=True),
        sa.Column("predicted_duration_min", sa.Integer(), nullable=True),
        sa.Column("predicted_num_loads", sa.Integer(), nullable=True),
        # Full structured JSONB
        sa.Column("predicted", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_pred_snap_org_plan", "plan_prediction_snapshots", ["org_id", "plan_id"])
    op.create_index("ix_pred_snap_created", "plan_prediction_snapshots", ["created_at"])

    # ---- plan_outcomes (MUTABLE ACTUALS) ----
    op.create_table(
        "plan_outcomes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", sa.String(64), nullable=False),
        sa.Column("prediction_snapshot_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        # Top-line actuals (Numeric for money)
        sa.Column("actual_revenue", sa.Numeric(12, 2), nullable=True),
        sa.Column("actual_fuel_spend", sa.Numeric(12, 2), nullable=True),
        sa.Column("actual_tolls", sa.Numeric(12, 2), nullable=True),
        sa.Column("actual_maintenance", sa.Numeric(12, 2), nullable=True),
        sa.Column("actual_other_costs", sa.Numeric(12, 2), nullable=True),
        sa.Column("actual_miles_loaded", sa.Integer(), nullable=True),
        sa.Column("actual_miles_deadhead", sa.Integer(), nullable=True),
        sa.Column("actual_drive_min", sa.Integer(), nullable=True),
        sa.Column("actual_wait_min", sa.Integer(), nullable=True),
        # Full JSONB
        sa.Column("actual", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_plan_outcome_org_plan", "plan_outcomes", ["org_id", "plan_id"])
    op.create_index("ix_plan_outcome_org_status", "plan_outcomes", ["org_id", "status"])


def downgrade():
    op.drop_table("plan_outcomes")
    op.drop_table("plan_prediction_snapshots")
