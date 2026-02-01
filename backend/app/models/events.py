"""
Audit logging models for tracking optimization requests
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from datetime import datetime
import uuid
from app.db.connection import Base


class RecommendationEvent(Base):
    """
    Audit log for every optimization request
    Stores full payload for replay and debugging
    """
    __tablename__ = "recommendation_events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    snapshot_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Connector metadata
    connector = Column(String(50), nullable=False)
    query_params = Column(JSONB, nullable=True)

    # Input/output tracking
    input_load_ids = Column(JSONB, nullable=False)  # List of load IDs analyzed
    output_top3 = Column(JSONB, nullable=False)     # List of {loadId, score, confidence}

    # Full request/response for replay capability
    full_payload = Column(JSONB, nullable=False)

    # Metrics
    loads_analyzed = Column(Integer, nullable=False, default=0)
    loads_feasible = Column(Integer, nullable=False, default=0)

    # Warnings/notes
    warnings = Column(JSONB, nullable=True)

    # Multi-tenant (Phase 2A)
    org_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)

    def __repr__(self):
        return f"<RecommendationEvent(id={self.id}, snapshot_id={self.snapshot_id}, timestamp={self.timestamp})>"


# Phase 0: New audit models for plan-based decision system

class PlanGenerationEvent(Base):
    """
    Audit log for every plan generation request
    Stores full payload for replay and debugging
    """
    __tablename__ = "plan_generation_events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    snapshot_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Plan generation parameters
    planning_horizon_days = Column(Integer, nullable=False)
    plans_generated = Column(Integer, nullable=False)

    # Full request/response for replay capability
    full_payload = Column(JSONB, nullable=False, comment="Complete request/response for replay")

    # Warnings/notes
    warnings = Column(JSONB, nullable=True)

    # Metrics
    loads_analyzed = Column(Integer, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)

    # Multi-tenant (Phase 2A)
    org_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)

    def __repr__(self):
        return f"<PlanGenerationEvent(id={self.id}, snapshot_id={self.snapshot_id}, plans={self.plans_generated})>"


class DecisionEvent(Base):
    """
    Audit log for when drivers accept/reject/modify plans
    Tracks decision-making patterns
    """
    __tablename__ = "decision_events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    plan_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    snapshot_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Decision type: accepted, rejected, modified
    decision_type = Column(String(20), nullable=False)

    # Why driver made this decision
    reason = Column(Text, nullable=True)

    # Complete plan + decision context for analysis
    full_context = Column(JSONB, nullable=False)

    # Multi-tenant (Phase 2A)
    org_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)

    def __repr__(self):
        return f"<DecisionEvent(id={self.id}, plan_id={self.plan_id}, decision={self.decision_type})>"
