"""
LoadSnapshot model — immutable raw + canonical load data (Phase 3A)
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, DateTime, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

from app.db.connection import Base


class LoadSnapshot(Base):
    __tablename__ = "load_snapshots"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(PG_UUID(as_uuid=True), nullable=False)
    source = Column(String(50), nullable=False)
    external_id = Column(String(255), nullable=False)

    # Immutable original response
    raw_payload = Column(JSONB, nullable=False)
    # Normalized CanonicalLoad JSON
    canonical = Column(JSONB, nullable=False)

    ingested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(String(20), nullable=False, default="active")  # active|covered|expired

    posted_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    # Denormalized for fast queries
    equipment = Column(String(50), nullable=True)
    pickup_city = Column(String(100), nullable=True)
    pickup_state = Column(String(10), nullable=True)
    delivery_city = Column(String(100), nullable=True)
    delivery_state = Column(String(10), nullable=True)
    pickup_lat = Column(Float, nullable=True)
    pickup_lng = Column(Float, nullable=True)
    delivery_lat = Column(Float, nullable=True)
    delivery_lng = Column(Float, nullable=True)
    rate_total = Column(Float, nullable=True)
    miles = Column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_source_external_id"),
        Index("ix_load_snapshots_org_status", "org_id", "status"),
        Index("ix_load_snapshots_pickup_state", "pickup_state"),
        Index("ix_load_snapshots_delivery_state", "delivery_state"),
    )
