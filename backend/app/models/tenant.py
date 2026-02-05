"""
Multi-tenant models: Organization, Truck, Route (Phase 2A)
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.connection import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    tier = Column(String(20), nullable=False, default="base")  # base, premium, enterprise
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Truck(Base):
    __tablename__ = "trucks"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(PG_UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    equipment_type = Column(String(50), default="reefer", nullable=False)
    home_base_city = Column(String(100), nullable=True)
    home_base_state = Column(String(2), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Route(Base):
    __tablename__ = "routes"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(PG_UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    source = Column(String(50), nullable=False, default="user_uploaded")
    external_id = Column(String(255), nullable=True)
    pickup_city = Column(String(100), nullable=False)
    pickup_state = Column(String(10), nullable=False)
    delivery_city = Column(String(100), nullable=False)
    delivery_state = Column(String(10), nullable=False)
    rate_total = Column(Float, nullable=False)
    miles = Column(Float, nullable=True)
    posted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
