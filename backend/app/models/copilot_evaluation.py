"""
CopilotEvaluation — audit trail for copilot plan evaluations (Phase 4.1)
"""
from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from datetime import datetime

from app.db.connection import Base


class CopilotEvaluation(Base):
    __tablename__ = "copilot_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(PG_UUID(as_uuid=True), nullable=False)
    plan_id = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False)  # ok | degraded | unknown
    signals = Column(JSONB, nullable=False, default=list)
    suggestions = Column(JSONB, nullable=False, default=list)
    explanations = Column(JSONB, nullable=False, default=list)
    meta = Column(JSONB, nullable=False, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    parent_plan_generation_event_id = Column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_copilot_eval_org_plan", "org_id", "plan_id"),
    )

    def __repr__(self):
        return f"<CopilotEvaluation(id={self.id}, plan_id={self.plan_id}, status={self.status})>"
