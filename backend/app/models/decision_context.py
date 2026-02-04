"""
Decision Context Snapshot model — Stratum 5D: Learning Loop

Captures trust + copilot state at decision time for post-mortem analysis.
Immutable after creation — never updated, only read.
"""
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from datetime import datetime
import uuid
from app.db.connection import Base


class DecisionContextSnapshot(Base):
    """
    Immutable snapshot of copilot + trust state at decision time.

    Purpose:
      - Enables "What we knew then" post-mortems
      - Correlates pre-decision warnings to actual outcomes
      - Audit trail for every accepted plan

    Created once on accept, never updated.
    """
    __tablename__ = "decision_context_snapshots"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    plan_id = Column(String(100), nullable=False, index=True)
    decision_event_id = Column(Integer, ForeignKey("decision_events.id"), nullable=False, index=True)

    # When snapshot was captured
    captured_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Trust state at decision time
    trust_confidence_score = Column(Integer, nullable=True)  # 0-100
    trust_confidence_label = Column(String(20), nullable=True)  # high/medium/low/unknown
    trust_warnings = Column(JSONB, nullable=True)  # List[RiskWarning] as dicts
    trust_explanations = Column(JSONB, nullable=True)  # List[str]
    trust_meta = Column(JSONB, nullable=True)  # TrustMeta as dict

    # Copilot state at decision time
    copilot_status = Column(String(20), nullable=True)  # ok/degraded/unknown
    copilot_signals = Column(JSONB, nullable=True)  # List[Signal] as dicts
    copilot_suggestions = Column(JSONB, nullable=True)  # List[Suggestion] as dicts
    copilot_explanations = Column(JSONB, nullable=True)  # List[str]

    # Calibration state at decision time
    calibration_sample_size = Column(Integer, nullable=True)
    calibration_profile_confidence = Column(Numeric(5, 4), nullable=True)  # 0.0000-1.0000
    calibration_applied = Column(String(10), nullable=True)  # yes/no/partial

    # Plan economics at decision time (from calibrated estimates if available)
    plan_revenue = Column(Numeric(12, 2), nullable=True)
    plan_costs = Column(Numeric(12, 2), nullable=True)
    plan_net_profit = Column(Numeric(12, 2), nullable=True)
    plan_duration_min = Column(Integer, nullable=True)
    plan_num_loads = Column(Integer, nullable=True)

    # Full context blob for future extensibility
    full_context = Column(JSONB, nullable=True)

    def __repr__(self):
        return f"<DecisionContextSnapshot(id={self.id}, plan_id={self.plan_id}, trust_label={self.trust_confidence_label})>"
