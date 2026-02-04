"""007_decision_context_snapshots — Stratum 5D: Learning Loop

Revision ID: 007_decision_context
Revises: 006_plan_outcomes
Create Date: 2026-02-04

Creates decision_context_snapshots table for capturing trust + copilot state
at decision time for post-mortem analysis.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007_decision_context"
down_revision = "006_plan_outcomes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_context_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("plan_id", sa.String(100), nullable=False, index=True),
        sa.Column("decision_event_id", sa.Integer, sa.ForeignKey("decision_events.id"), nullable=False, index=True),
        sa.Column("captured_at", sa.DateTime, nullable=False),

        # Trust state
        sa.Column("trust_confidence_score", sa.Integer, nullable=True),
        sa.Column("trust_confidence_label", sa.String(20), nullable=True),
        sa.Column("trust_warnings", postgresql.JSONB, nullable=True),
        sa.Column("trust_explanations", postgresql.JSONB, nullable=True),
        sa.Column("trust_meta", postgresql.JSONB, nullable=True),

        # Copilot state
        sa.Column("copilot_status", sa.String(20), nullable=True),
        sa.Column("copilot_signals", postgresql.JSONB, nullable=True),
        sa.Column("copilot_suggestions", postgresql.JSONB, nullable=True),
        sa.Column("copilot_explanations", postgresql.JSONB, nullable=True),

        # Calibration state
        sa.Column("calibration_sample_size", sa.Integer, nullable=True),
        sa.Column("calibration_profile_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("calibration_applied", sa.String(10), nullable=True),

        # Plan economics at decision time
        sa.Column("plan_revenue", sa.Numeric(12, 2), nullable=True),
        sa.Column("plan_costs", sa.Numeric(12, 2), nullable=True),
        sa.Column("plan_net_profit", sa.Numeric(12, 2), nullable=True),
        sa.Column("plan_duration_min", sa.Integer, nullable=True),
        sa.Column("plan_num_loads", sa.Integer, nullable=True),

        # Full context blob
        sa.Column("full_context", postgresql.JSONB, nullable=True),
    )

    # Composite index for common query pattern
    op.create_index(
        "ix_decision_context_org_plan",
        "decision_context_snapshots",
        ["org_id", "plan_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_decision_context_org_plan", table_name="decision_context_snapshots")
    op.drop_table("decision_context_snapshots")
