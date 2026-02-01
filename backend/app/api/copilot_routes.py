"""
Copilot API routes (Phase 4)

GET /api/copilot/plan_status — evaluate plan degradation
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_org_id
from app.db.connection import get_db
from app.copilot.schemas import CopilotMeta, CopilotResponse
from app.copilot.repository import find_plan_by_id, check_load_active
from app.copilot.evaluator import evaluate_plan
from app.intel.repository import (
    get_lane_statistic,
    get_market_statistic,
    get_destination_score,
)
from app.intel.time_windows import resolve_window

logger = logging.getLogger(__name__)

copilot_router = APIRouter(tags=["copilot"])


@copilot_router.get("/copilot/plan_status", response_model=CopilotResponse)
def get_plan_status(
    plan_id: str = Query(..., description="UUID of the plan to evaluate"),
    window_lane: str = Query("6h", description="Window for lane intel"),
    window_market: str = Query("6h", description="Window for market intel"),
    window_destination: str = Query("24h", description="Window for destination intel"),
    as_of: Optional[str] = Query(None, description="ISO timestamp for historical replay"),
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    windows = {
        "lane": window_lane,
        "market": window_market,
        "destination": window_destination,
    }
    base_meta = CopilotMeta(
        org_id=org_id,
        plan_id=plan_id,
        as_of=now,
        evaluated_at=now,
        windows=windows,
        data_sources={},
        offline=False,
    )

    # 1. Find plan
    try:
        plan = find_plan_by_id(db, org_id, plan_id)
    except Exception as exc:
        logger.warning("DB error fetching plan: %s", exc)
        base_meta.offline = True
        return CopilotResponse(
            meta=base_meta,
            status="unknown",
            explanations=["Could not retrieve plan. Database may be unavailable."],
        )

    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found.")

    # 2. Extract geohashes from first load
    loads = plan.get("loads", [])
    if not loads:
        return CopilotResponse(
            meta=base_meta,
            status="unknown",
            explanations=["Plan has no loads."],
        )

    first_load_in_plan = loads[0]
    load = first_load_in_plan.get("load", first_load_in_plan)
    origin_gh = load.get("pickup_geohash")
    dest_gh = load.get("delivery_geohash")

    if not origin_gh or not dest_gh:
        return CopilotResponse(
            meta=base_meta,
            status="unknown",
            explanations=["Plan loads missing geohash data. Intel evaluation not possible."],
        )

    # 3. Fetch intel data (graceful on failure)
    lane_stat = None
    market_stat = None
    dest_score = None
    loads_active: dict = {}
    intel_source = "unknown"

    try:
        lane_start, lane_end, _ = resolve_window(window_lane, as_of=as_of)
        market_start, market_end, _ = resolve_window(window_market, as_of=as_of)
        dest_start, dest_end, _ = resolve_window(window_destination, as_of=as_of)

        lane_stat = get_lane_statistic(
            db, org_id, origin_gh, dest_gh, lane_start, lane_end
        )
        market_stat = get_market_statistic(
            db, org_id, dest_gh, market_start, market_end
        )
        dest_score = get_destination_score(
            db, org_id, dest_gh, dest_start, dest_end
        )

        if lane_stat and lane_stat.source:
            intel_source = lane_stat.source

        # Check load availability for all loads
        for lip in loads:
            ld = lip.get("load", lip)
            source = ld.get("source", "")
            ext_id = ld.get("external_id", "")
            key = f"{source}/{ext_id}" if source and ext_id else ld.get("id", "unknown")
            if source and ext_id:
                loads_active[key] = check_load_active(db, org_id, source, ext_id)
            else:
                loads_active[key] = True  # Can't check, assume ok

    except Exception as exc:
        logger.warning("Intel fetch failed for copilot: %s", exc)
        base_meta.offline = True
        return CopilotResponse(
            meta=base_meta,
            status="unknown",
            explanations=["Intel unavailable. Analytics service may be offline."],
        )

    base_meta.data_sources = {"intel_source": intel_source}

    # 4. Evaluate
    status, signals, suggestions, explanations = evaluate_plan(
        plan=plan,
        lane_rate_p50=lane_stat.rate_p50 if lane_stat else None,
        lane_rate_p75=lane_stat.rate_p75 if lane_stat else None,
        lane_time_to_cover=lane_stat.time_to_cover_p50_minutes if lane_stat else None,
        lane_load_count=lane_stat.load_count if lane_stat else None,
        market_temperature=market_stat.market_temperature if market_stat else None,
        efficiency_score=dest_score.efficiency_score if dest_score else None,
        loads_active=loads_active,
    )

    return CopilotResponse(
        meta=base_meta,
        status=status,
        signals=signals,
        suggestions=suggestions,
        explanations=explanations,
    )
