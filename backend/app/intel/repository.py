"""
Repository layer — all DB reads for intelligence APIs (Phase 3C)

No analytics computation. Read-only queries against Phase 3B tables.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models.analytics import LaneStatistic, MarketStatistic, DestinationScore


def _resolve_source(
    db: Session,
    model,
    org_id: str,
    source: Optional[str],
    window_start: datetime,
    window_end: datetime,
    **extra_filters,
) -> Optional[str]:
    """
    If source is provided, return it. Otherwise find the most recently
    computed source for the given window.
    """
    if source:
        return source

    q = (
        db.query(model.source)
        .filter(
            model.org_id == org_id,
            model.window_start == window_start,
            model.window_end == window_end,
        )
    )
    for col, val in extra_filters.items():
        q = q.filter(getattr(model, col) == val)

    row = q.order_by(desc(model.computed_at)).first()
    return row[0] if row else None


def get_lane_statistic(
    db: Session,
    org_id: str,
    origin_geohash: str,
    destination_geohash: str,
    window_start: datetime,
    window_end: datetime,
    equipment_type: Optional[str] = None,
    source: Optional[str] = None,
) -> Optional[LaneStatistic]:
    """Fetch a single lane_statistics row matching exact window."""
    resolved_source = _resolve_source(
        db, LaneStatistic, org_id, source, window_start, window_end,
        origin_geohash=origin_geohash,
        destination_geohash=destination_geohash,
    )
    if not resolved_source:
        return None

    q = (
        db.query(LaneStatistic)
        .filter(
            LaneStatistic.org_id == org_id,
            LaneStatistic.origin_geohash == origin_geohash,
            LaneStatistic.destination_geohash == destination_geohash,
            LaneStatistic.window_start == window_start,
            LaneStatistic.window_end == window_end,
            LaneStatistic.source == resolved_source,
        )
    )
    if equipment_type:
        q = q.filter(LaneStatistic.equipment_type == equipment_type)

    return q.first()


def get_market_statistic(
    db: Session,
    org_id: str,
    market_geohash: str,
    window_start: datetime,
    window_end: datetime,
    source: Optional[str] = None,
) -> Optional[MarketStatistic]:
    """Fetch a single market_statistics row matching exact window."""
    resolved_source = _resolve_source(
        db, MarketStatistic, org_id, source, window_start, window_end,
        market_geohash=market_geohash,
    )
    if not resolved_source:
        return None

    return (
        db.query(MarketStatistic)
        .filter(
            MarketStatistic.org_id == org_id,
            MarketStatistic.market_geohash == market_geohash,
            MarketStatistic.window_start == window_start,
            MarketStatistic.window_end == window_end,
            MarketStatistic.source == resolved_source,
        )
        .first()
    )


def get_destination_score(
    db: Session,
    org_id: str,
    destination_geohash: str,
    window_start: datetime,
    window_end: datetime,
    source: Optional[str] = None,
) -> Optional[DestinationScore]:
    """Fetch a single destination_scores row matching exact window."""
    resolved_source = _resolve_source(
        db, DestinationScore, org_id, source, window_start, window_end,
        destination_geohash=destination_geohash,
    )
    if not resolved_source:
        return None

    return (
        db.query(DestinationScore)
        .filter(
            DestinationScore.org_id == org_id,
            DestinationScore.destination_geohash == destination_geohash,
            DestinationScore.window_start == window_start,
            DestinationScore.window_end == window_end,
            DestinationScore.source == resolved_source,
        )
        .first()
    )


def get_top_destinations(
    db: Session,
    org_id: str,
    window_start: datetime,
    window_end: datetime,
    source: Optional[str] = None,
    limit: int = 10,
) -> List[DestinationScore]:
    """Fetch top destinations by efficiency_score for corridor endpoint."""
    # Resolve source from any destination row in this window
    resolved_source = _resolve_source(
        db, DestinationScore, org_id, source, window_start, window_end,
    )
    if not resolved_source:
        return []

    return (
        db.query(DestinationScore)
        .filter(
            DestinationScore.org_id == org_id,
            DestinationScore.window_start == window_start,
            DestinationScore.window_end == window_end,
            DestinationScore.source == resolved_source,
            DestinationScore.efficiency_score.isnot(None),
        )
        .order_by(desc(DestinationScore.efficiency_score))
        .limit(limit)
        .all()
    )


def get_market_for_geohash(
    db: Session,
    org_id: str,
    market_geohash: str,
    window_start: datetime,
    window_end: datetime,
    source: Optional[str] = None,
) -> Optional[MarketStatistic]:
    """Alias for get_market_statistic, used by corridor join."""
    return get_market_statistic(db, org_id, market_geohash, window_start, window_end, source)


def get_table_health(
    db: Session,
    org_id: str,
) -> dict:
    """Get latest computed_at and row counts for each analytics table."""
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    result = {}

    for model, name in [
        (LaneStatistic, "lane_statistics"),
        (MarketStatistic, "market_statistics"),
        (DestinationScore, "destination_scores"),
    ]:
        latest = (
            db.query(func.max(model.computed_at))
            .filter(model.org_id == org_id)
            .scalar()
        )
        count_24h = (
            db.query(func.count(model.id))
            .filter(
                model.org_id == org_id,
                model.computed_at >= cutoff_24h,
            )
            .scalar()
        )
        freshness = None
        if latest:
            if latest.tzinfo is None:
                latest = latest.replace(tzinfo=timezone.utc)
            freshness = (now - latest).total_seconds()

        result[name] = {
            "latest_computed_at": latest,
            "rows_last_24h": count_24h or 0,
            "freshness_seconds": round(freshness, 1) if freshness is not None else None,
        }

    return result
