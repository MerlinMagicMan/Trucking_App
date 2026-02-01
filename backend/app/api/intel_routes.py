"""
Intelligence API endpoints — read-only over Phase 3B analytics tables (Phase 3C)

No analytics computation. No ingestion. No UI.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.api.dependencies import get_org_id
from app.intel.time_windows import resolve_window
from app.intel.repository import (
    get_lane_statistic,
    get_market_statistic,
    get_destination_score,
    get_top_destinations,
    get_market_for_geohash,
    get_table_health,
)
from app.intel.negotiation import compute_negotiation
from app.intel.schemas import (
    IntelMeta,
    LaneIntelResponse,
    MarketIntelResponse,
    DestinationIntelResponse,
    NegotiationIntelResponse,
    CorridorIntelResponse,
    CorridorDestination,
    IntelHealthResponse,
    TableHealth,
)

intel_router = APIRouter(prefix="/intel", tags=["intelligence"])


def _freshness(computed_at: Optional[datetime]) -> Optional[float]:
    """Seconds since computed_at."""
    if computed_at is None:
        return None
    ca = computed_at if computed_at.tzinfo else computed_at.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - ca).total_seconds(), 1)


# --------------------------------------------------------------------------
# 1. Lane intelligence
# --------------------------------------------------------------------------

@intel_router.get("/lane", response_model=LaneIntelResponse)
async def lane_intel(
    origin_geohash: str = Query(...),
    destination_geohash: str = Query(...),
    window: str = Query("6h"),
    as_of: Optional[str] = Query(None),
    equipment_type: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    window_start, window_end, window_label = resolve_window(window, as_of)

    row = get_lane_statistic(
        db, org_id, origin_geohash, destination_geohash,
        window_start, window_end, equipment_type, source,
    )

    meta = IntelMeta(
        org_id=org_id,
        window=window_label,
        window_start=window_start,
        window_end=window_end,
        source=row.source if row else (source or "unknown"),
        computed_at=row.computed_at if row else None,
        data_freshness_seconds=_freshness(row.computed_at) if row else None,
        sample_size=row.load_count if row else 0,
    )

    if not row:
        return LaneIntelResponse(
            meta=meta, data=None,
            explanations=[
                f"No lane data for {origin_geohash} → {destination_geohash} in {window_label} window.",
                "Analytics may not have run yet, or no loads observed on this lane.",
            ],
        )

    data = {
        "rate_p25": row.rate_p25,
        "rate_p50": row.rate_p50,
        "rate_p75": row.rate_p75,
        "rate_p90": row.rate_p90,
        "avg_miles": row.avg_miles,
        "avg_rate_per_mile": row.avg_rate_per_mile,
        "time_to_cover_p50_minutes": row.time_to_cover_p50_minutes,
        "volatility_score": row.volatility_score,
        "load_count": row.load_count,
    }

    explanations = []
    if row.rate_p50:
        explanations.append(
            f"Median rate on this lane is ${row.rate_p50:,.0f} "
            f"(range: ${row.rate_p25:,.0f} – ${row.rate_p90:,.0f})."
        )
    if row.avg_rate_per_mile:
        explanations.append(f"Average rate per mile: ${row.avg_rate_per_mile:.2f}/mi.")
    if row.time_to_cover_p50_minutes:
        explanations.append(f"Typical time to cover: {row.time_to_cover_p50_minutes:.0f} minutes.")
    explanations.append(f"Based on {row.load_count} loads in {window_label} window.")

    return LaneIntelResponse(meta=meta, data=data, explanations=explanations)


# --------------------------------------------------------------------------
# 2. Market intelligence
# --------------------------------------------------------------------------

@intel_router.get("/market", response_model=MarketIntelResponse)
async def market_intel(
    market_geohash: str = Query(...),
    window: str = Query("6h"),
    as_of: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    window_start, window_end, window_label = resolve_window(window, as_of)

    row = get_market_statistic(db, org_id, market_geohash, window_start, window_end, source)

    meta = IntelMeta(
        org_id=org_id,
        window=window_label,
        window_start=window_start,
        window_end=window_end,
        source=row.source if row else (source or "unknown"),
        computed_at=row.computed_at if row else None,
        data_freshness_seconds=_freshness(row.computed_at) if row else None,
        sample_size=row.new_loads_count if row else 0,
    )

    if not row:
        return MarketIntelResponse(
            meta=meta, data=None,
            explanations=[
                f"No market data for geohash {market_geohash} in {window_label} window.",
                "Analytics may not have run yet for this region.",
            ],
        )

    data = {
        "active_load_count_avg": row.active_load_count_avg,
        "new_loads_count": row.new_loads_count,
        "expired_loads_count": row.expired_loads_count,
        "reload_depth": row.reload_depth,
        "market_temperature": row.market_temperature,
    }

    explanations = []
    temp_label = {"hot": "hot (high demand)", "cold": "cold (low demand)", "neutral": "balanced"}.get(
        row.market_temperature, row.market_temperature
    )
    explanations.append(f"Market is {temp_label}.")
    explanations.append(
        f"{row.active_load_count_avg:.0f} average active loads, "
        f"{row.new_loads_count} new, {row.expired_loads_count} expired in window."
    )
    if row.reload_depth:
        explanations.append(f"Reload depth: {row.reload_depth:.2f}.")

    return MarketIntelResponse(meta=meta, data=data, explanations=explanations)


# --------------------------------------------------------------------------
# 3. Destination intelligence
# --------------------------------------------------------------------------

@intel_router.get("/destination", response_model=DestinationIntelResponse)
async def destination_intel(
    destination_geohash: str = Query(...),
    window: str = Query("24h"),
    as_of: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    window_start, window_end, window_label = resolve_window(window, as_of)

    row = get_destination_score(db, org_id, destination_geohash, window_start, window_end, source)

    meta = IntelMeta(
        org_id=org_id,
        window=window_label,
        window_start=window_start,
        window_end=window_end,
        source=row.source if row else (source or "unknown"),
        computed_at=row.computed_at if row else None,
        data_freshness_seconds=_freshness(row.computed_at) if row else None,
        sample_size=None,
    )

    if not row:
        return DestinationIntelResponse(
            meta=meta, data=None,
            explanations=[
                f"No destination data for geohash {destination_geohash} in {window_label} window.",
                "Analytics may not have run yet for this destination.",
            ],
        )

    data = {
        "efficiency_score": row.efficiency_score,
        "reload_probability": row.reload_probability,
        "avg_time_to_first_reload_minutes": row.avg_time_to_first_reload_minutes,
        "volatility_score": row.volatility_score,
        "explanation_components": row.explanation,
    }

    explanations = []
    if row.efficiency_score is not None:
        grade = "A+" if row.efficiency_score >= 80 else "A" if row.efficiency_score >= 65 else "B" if row.efficiency_score >= 50 else "C" if row.efficiency_score >= 35 else "D"
        explanations.append(f"Destination efficiency: {row.efficiency_score:.0f}/100 (grade {grade}).")
    if row.reload_probability is not None:
        explanations.append(f"Reload probability: {row.reload_probability:.0%}.")
    if row.avg_time_to_first_reload_minutes is not None:
        explanations.append(f"Average time to first reload: {row.avg_time_to_first_reload_minutes:.0f} minutes.")

    return DestinationIntelResponse(meta=meta, data=data, explanations=explanations)


# --------------------------------------------------------------------------
# 4. Negotiation intelligence
# --------------------------------------------------------------------------

@intel_router.get("/negotiation", response_model=NegotiationIntelResponse)
async def negotiation_intel(
    origin_geohash: str = Query(...),
    destination_geohash: str = Query(...),
    offered_rate_usd: float = Query(...),
    window: str = Query("6h"),
    as_of: Optional[str] = Query(None),
    equipment_type: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    window_start, window_end, window_label = resolve_window(window, as_of)

    row = get_lane_statistic(
        db, org_id, origin_geohash, destination_geohash,
        window_start, window_end, equipment_type, source,
    )

    meta = IntelMeta(
        org_id=org_id,
        window=window_label,
        window_start=window_start,
        window_end=window_end,
        source=row.source if row else (source or "unknown"),
        computed_at=row.computed_at if row else None,
        data_freshness_seconds=_freshness(row.computed_at) if row else None,
        sample_size=row.load_count if row else 0,
    )

    neg = compute_negotiation(
        offered_rate_usd=offered_rate_usd,
        rate_p25=row.rate_p25 if row else None,
        rate_p50=row.rate_p50 if row else None,
        rate_p75=row.rate_p75 if row else None,
        rate_p90=row.rate_p90 if row else None,
        time_to_cover_p50_minutes=row.time_to_cover_p50_minutes if row else None,
        load_count=row.load_count if row else 0,
    )

    data = {
        "position": neg["position"],
        "suggested_counter": neg["suggested_counter"],
        "suggested_accept": neg["suggested_accept"],
        "walk_away": neg["walk_away"],
        "percentile_position": neg["percentile_position"],
        "offered_rate_usd": offered_rate_usd,
    } if neg["position"] is not None else None

    return NegotiationIntelResponse(
        meta=meta, data=data, explanations=neg["explanations"],
    )


# --------------------------------------------------------------------------
# 5. Corridor intelligence
# --------------------------------------------------------------------------

@intel_router.get("/corridor", response_model=CorridorIntelResponse)
async def corridor_intel(
    origin_geohash: str = Query(...),
    radius_miles: int = Query(150),
    window: str = Query("24h"),
    as_of: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    limit: int = Query(10),
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    window_start, window_end, window_label = resolve_window(window, as_of)

    # Get top destinations by efficiency_score (all destinations, not filtered by origin radius)
    # Radius filtering would require geohash distance which is beyond scope;
    # we return top destinations and let the caller filter.
    destinations = get_top_destinations(
        db, org_id, window_start, window_end, source, limit,
    )

    resolved_source = destinations[0].source if destinations else (source or "unknown")

    meta = IntelMeta(
        org_id=org_id,
        window=window_label,
        window_start=window_start,
        window_end=window_end,
        source=resolved_source,
        computed_at=destinations[0].computed_at if destinations else None,
        data_freshness_seconds=_freshness(destinations[0].computed_at) if destinations else None,
        sample_size=len(destinations),
    )

    if not destinations:
        return CorridorIntelResponse(
            meta=meta, data=None,
            explanations=["No destination scores available in this window."],
        )

    # Enrich with market data where available
    result = []
    for dest in destinations:
        market = get_market_for_geohash(
            db, org_id, dest.destination_geohash, window_start, window_end, resolved_source,
        )
        result.append(CorridorDestination(
            destination_geohash=dest.destination_geohash,
            efficiency_score=dest.efficiency_score,
            reload_probability=dest.reload_probability,
            avg_time_to_first_reload_minutes=dest.avg_time_to_first_reload_minutes,
            market_temperature=market.market_temperature if market else None,
            active_load_count_avg=market.active_load_count_avg if market else None,
        ))

    explanations = [
        f"Top {len(result)} destinations ranked by efficiency score.",
        f"Window: {window_label} ending {window_end.isoformat()}.",
    ]

    return CorridorIntelResponse(meta=meta, data=result, explanations=explanations)


# --------------------------------------------------------------------------
# 6. Health
# --------------------------------------------------------------------------

@intel_router.get("/health", response_model=IntelHealthResponse)
async def intel_health(
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    health = get_table_health(db, org_id)

    tables = []
    for table_name, info in health.items():
        tables.append(TableHealth(
            table=table_name,
            latest_computed_at=info["latest_computed_at"],
            rows_last_24h=info["rows_last_24h"],
            freshness_seconds=info["freshness_seconds"],
        ))

    return IntelHealthResponse(tables=tables)
