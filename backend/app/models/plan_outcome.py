"""
Plan Outcomes — prediction snapshots + actuals tracking (Phase 5, Stratum 4A)

Two tables:
1. plan_prediction_snapshots — IMMUTABLE frozen prediction at acceptance time
2. plan_outcomes — MUTABLE actuals entered after plan execution
"""
import uuid
from sqlalchemy import Column, Integer, String, DateTime, Text, Index, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from datetime import datetime

from app.db.connection import Base


class PlanPredictionSnapshot(Base):
    """
    Immutable record of what the engine predicted at the time a plan was accepted.
    Append-only — never updated.
    """
    __tablename__ = "plan_prediction_snapshots"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(PG_UUID(as_uuid=True), nullable=False)
    plan_id = Column(String(64), nullable=False)
    plan_generation_event_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Top-line predicted numbers as columns (Numeric for money — no floats)
    predicted_revenue = Column(Numeric(12, 2), nullable=True)
    predicted_costs = Column(Numeric(12, 2), nullable=True)
    predicted_net_profit = Column(Numeric(12, 2), nullable=True)
    predicted_profit_per_day = Column(Numeric(12, 2), nullable=True)
    predicted_miles_total = Column(Integer, nullable=True)
    predicted_miles_deadhead = Column(Integer, nullable=True)
    predicted_duration_min = Column(Integer, nullable=True)
    predicted_num_loads = Column(Integer, nullable=True)

    # Full structured JSONB for detailed breakdown + audit trail
    predicted = Column(JSONB, nullable=False, default=dict, comment=(
        "Canonical prediction structure: economics_summary, time_summary, "
        "structure_summary, assumptions"
    ))

    __table_args__ = (
        Index("ix_pred_snap_org_plan", "org_id", "plan_id"),
    )

    def __repr__(self):
        return f"<PlanPredictionSnapshot(id={self.id}, plan_id={self.plan_id})>"


class PlanOutcome(Base):
    """
    Mutable record of actual results for a plan execution.
    Updated as actuals come in (manual entry initially).
    """
    __tablename__ = "plan_outcomes"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(PG_UUID(as_uuid=True), nullable=False)
    plan_id = Column(String(64), nullable=False)
    prediction_snapshot_id = Column(PG_UUID(as_uuid=True), nullable=True)

    # Status: pending | partial | complete
    status = Column(String(20), nullable=False, default="pending")
    source = Column(String(20), nullable=False, default="manual")

    # Top-line actual numbers as columns (Numeric for money)
    actual_revenue = Column(Numeric(12, 2), nullable=True)
    actual_fuel_spend = Column(Numeric(12, 2), nullable=True)
    actual_tolls = Column(Numeric(12, 2), nullable=True)
    actual_maintenance = Column(Numeric(12, 2), nullable=True)
    actual_other_costs = Column(Numeric(12, 2), nullable=True)
    actual_miles_loaded = Column(Integer, nullable=True)
    actual_miles_deadhead = Column(Integer, nullable=True)
    actual_drive_min = Column(Integer, nullable=True)
    actual_wait_min = Column(Integer, nullable=True)

    # Full structured JSONB for detailed actuals
    actual = Column(JSONB, nullable=False, default=dict, comment=(
        "Actual results: revenue_received, fuel_spend, tolls, repairs_maintenance, "
        "other_costs, actual_start_time, actual_end_time, actual_drive_min, "
        "actual_wait_min, miles_loaded, miles_deadhead, notes"
    ))

    notes = Column(Text, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)

    # Future: field-level manual lock (prevents auto-ingestion from overwriting specific fields)
    locked_fields = Column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_plan_outcome_org_plan", "org_id", "plan_id"),
        Index("ix_plan_outcome_org_status", "org_id", "status"),
    )

    def __repr__(self):
        return f"<PlanOutcome(id={self.id}, plan_id={self.plan_id}, status={self.status})>"
