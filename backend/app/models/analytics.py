"""
Analytics derived tables — Phase 3B

All tables are computed from load_snapshots. Never mutated by user actions.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, Integer, DateTime, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

from app.db.connection import Base


class LaneStatistic(Base):
    __tablename__ = "lane_statistics"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(PG_UUID(as_uuid=True), nullable=False)
    source = Column(Text, nullable=False)
    equipment_type = Column(Text, nullable=True)

    origin_geohash = Column(Text, nullable=False)
    destination_geohash = Column(Text, nullable=False)

    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    computed_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Metrics
    load_count = Column(Integer, nullable=False)
    rate_p25 = Column(Float, nullable=True)
    rate_p50 = Column(Float, nullable=True)
    rate_p75 = Column(Float, nullable=True)
    rate_p90 = Column(Float, nullable=True)
    avg_miles = Column(Float, nullable=True)
    avg_rate_per_mile = Column(Float, nullable=True)
    time_to_cover_p50_minutes = Column(Float, nullable=True)
    volatility_score = Column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "org_id", "origin_geohash", "destination_geohash",
            "equipment_type", "window_start", "window_end", "source",
            name="uq_lane_stat_window",
        ),
        Index("ix_lane_stat_lane_window", "org_id", "origin_geohash", "destination_geohash", "window_end"),
        Index("ix_lane_stat_window", "org_id", "window_start", "window_end"),
        Index("ix_lane_stat_computed", "org_id", "computed_at"),
    )


class MarketStatistic(Base):
    __tablename__ = "market_statistics"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(PG_UUID(as_uuid=True), nullable=False)
    source = Column(Text, nullable=False)

    market_geohash = Column(Text, nullable=False)

    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    computed_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Metrics
    active_load_count_avg = Column(Float, nullable=False)
    new_loads_count = Column(Integer, nullable=False)
    expired_loads_count = Column(Integer, nullable=False)
    reload_depth = Column(Float, nullable=True)
    market_temperature = Column(Text, nullable=True)  # cold|neutral|hot

    __table_args__ = (
        UniqueConstraint(
            "org_id", "market_geohash", "window_start", "window_end", "source",
            name="uq_market_stat_window",
        ),
        Index("ix_market_stat_geo_window", "org_id", "market_geohash", "window_end"),
        Index("ix_market_stat_computed", "org_id", "computed_at"),
    )


class DestinationScore(Base):
    __tablename__ = "destination_scores"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(PG_UUID(as_uuid=True), nullable=False)
    source = Column(Text, nullable=False)

    destination_geohash = Column(Text, nullable=False)

    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    computed_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Metrics
    reload_probability = Column(Float, nullable=True)  # 0..1
    avg_time_to_first_reload_minutes = Column(Float, nullable=True)
    efficiency_score = Column(Float, nullable=True)  # 0..100
    volatility_score = Column(Float, nullable=True)
    explanation = Column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "org_id", "destination_geohash", "window_start", "window_end", "source",
            name="uq_dest_score_window",
        ),
        Index("ix_dest_score_geo_window", "org_id", "destination_geohash", "window_end"),
    )
