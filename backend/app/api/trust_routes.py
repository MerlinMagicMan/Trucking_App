"""
Trust API routes — Stratum 5C

GET /api/trust/report — org-scoped trust report for a plan.
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_org_id
from app.db.connection import get_db
from app.copilot.repository import find_plan_by_id
from app.calibration.profile import build_calibration_profile, CAL_WINDOW_DAYS_DEFAULT
from app.trust.schemas import PlanTrustReport, TrustMeta, RiskWarning
from app.trust.engine import (
    dec,
    compute_adjustment_pct,
    compute_complexity_penalty,
    compute_offline_penalty,
    compute_volatility_penalty,
    compute_adjustment_penalty,
    compute_confidence_score,
    label_confidence,
    build_warnings,
    build_explanations,
)

logger = logging.getLogger(__name__)

trust_router = APIRouter(tags=["trust"])


def build_trust_report_for_plan(
    db: Session,
    org_id: str,
    plan_dict: Dict[str, Any],
    window_days: int = CAL_WINDOW_DAYS_DEFAULT,
    offline: bool = False,
    missing_intel_kinds: Optional[List[str]] = None,
    copilot_signals: Optional[List[Dict[str, Any]]] = None,
) -> PlanTrustReport:
    """Build trust report for a plan. Shared by trust_routes and copilot_routes."""
    plan_id = plan_dict.get("plan_id", "unknown")
    missing_intel_kinds = missing_intel_kinds or []

    # Load calibration profile
    try:
        cal_profile = build_calibration_profile(db, org_id, window_days)
    except Exception as e:
        logger.warning(f"Failed to build calibration profile: {e}")
        cal_profile = None

    # Extract plan estimates
    estimates_raw = plan_dict.get("estimates_raw", {})
    estimates_calibrated = plan_dict.get("estimates_calibrated")
    calibration_meta = plan_dict.get("calibration_meta", {})

    # If no estimates_raw, build from plan fields (older events)
    if not estimates_raw:
        estimates_raw = {
            "revenue": str(plan_dict.get("total_revenue_usd", 0)),
            "costs": str(plan_dict.get("total_costs_usd", 0)),
            "net_profit": str(plan_dict.get("net_profit_usd", 0)),
            "miles": str(sum(
                (l.get("deadhead_miles", 0) + (l.get("load", {}).get("miles") or 0))
                for l in plan_dict.get("loads", [])
            )),
            "duration_min": str(sum(
                b.get("duration_min", 0) for b in plan_dict.get("time_blocks", [])
            )),
            "profit_per_day": str(plan_dict.get("profit_per_day_usd", 0)),
        }

    # Compute adjustment percentages
    if estimates_calibrated:
        adjustment_pct = compute_adjustment_pct(estimates_raw, estimates_calibrated)
    else:
        adjustment_pct = {k: Decimal("0") for k in ["revenue", "costs", "net_profit", "miles", "duration_min"]}

    # Extract volatility from calibration profile
    if cal_profile:
        volatility_pct = cal_profile.volatility_pct_by_metric
        profile_confidence = dec(cal_profile.confidence)
        sample_size = cal_profile.sample_size
    else:
        volatility_pct = {}
        profile_confidence = None
        sample_size = 0

    # Extract plan complexity
    duration_min = dec(estimates_calibrated.get("duration_min", "0") if estimates_calibrated
                       else estimates_raw.get("duration_min", "0"))
    num_loads = len(plan_dict.get("loads", []))
    if num_loads == 0:
        num_loads = 1

    # Compute penalties
    volatility_penalty = compute_volatility_penalty(volatility_pct)
    adjustment_penalty = compute_adjustment_penalty(adjustment_pct)
    complexity_penalty = compute_complexity_penalty(duration_min, num_loads)
    offline_penalty = compute_offline_penalty(offline, len(missing_intel_kinds))

    # Compute score and label
    confidence_score = compute_confidence_score(
        profile_confidence, volatility_penalty, adjustment_penalty,
        complexity_penalty, offline_penalty,
    )
    confidence_label = label_confidence(confidence_score, offline, sample_size)

    # Build warnings
    warnings = build_warnings(
        sample_size=sample_size,
        profile_confidence=profile_confidence,
        volatility_pct=volatility_pct,
        adjustment_pct=adjustment_pct,
        offline=offline,
        missing_intel_kinds=missing_intel_kinds,
        plan_duration_min=duration_min,
        num_loads=num_loads,
        copilot_signals=copilot_signals,
        calibration_meta=calibration_meta,
    )

    # Build explanations
    explanations = build_explanations(
        sample_size=sample_size,
        window_days=window_days,
        profile_confidence=profile_confidence,
        volatility_penalty=volatility_penalty,
        adjustment_penalty=adjustment_penalty,
        complexity_penalty=complexity_penalty,
        offline_penalty=offline_penalty,
        confidence_score=confidence_score,
        confidence_label=confidence_label,
    )

    # Build meta
    meta = TrustMeta(
        org_id=org_id,
        plan_id=plan_id,
        computed_at=datetime.now(timezone.utc),
        window_days=window_days,
        offline=offline,
        sample_size=sample_size,
        profile_confidence=str(profile_confidence) if profile_confidence else "0",
        volatility_pct={k: str(v) for k, v in volatility_pct.items()},
        used_calibrated=estimates_calibrated is not None and calibration_meta.get("applied", False),
    )

    return PlanTrustReport(
        confidence_score=confidence_score,
        confidence_label=confidence_label,
        warnings=warnings,
        explanations=explanations,
        meta=meta,
    )


@trust_router.get("/trust/report")
def get_trust_report(
    plan_id: str = Query(..., description="Plan ID to evaluate"),
    window_days: int = Query(CAL_WINDOW_DAYS_DEFAULT, ge=1, le=365),
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Return trust report for a plan."""
    offline = False
    missing_intel_kinds: List[str] = []

    # Find plan
    try:
        plan_dict = find_plan_by_id(db, org_id, plan_id)
    except Exception as e:
        logger.warning(f"DB error fetching plan: {e}")
        offline = True
        plan_dict = None

    if plan_dict is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found.")

    # Check intel availability (best-effort)
    try:
        from app.intel.repository import get_lane_statistic, get_market_statistic, get_destination_score
        from app.intel.time_windows import resolve_window

        loads = plan_dict.get("loads", [])
        if loads:
            first_load = loads[0].get("load", loads[0])
            origin_gh = first_load.get("pickup_geohash")
            dest_gh = first_load.get("delivery_geohash")

            if origin_gh and dest_gh:
                start, end, _ = resolve_window("6h")
                lane = get_lane_statistic(db, org_id, origin_gh, dest_gh, start, end)
                market = get_market_statistic(db, org_id, dest_gh, start, end)
                dest = get_destination_score(db, org_id, dest_gh, start, end)

                if lane is None:
                    missing_intel_kinds.append("lane")
                if market is None:
                    missing_intel_kinds.append("market")
                if dest is None:
                    missing_intel_kinds.append("destination")
    except Exception as e:
        logger.warning(f"Intel check failed: {e}")
        offline = True

    report = build_trust_report_for_plan(
        db, org_id, plan_dict,
        window_days=window_days,
        offline=offline,
        missing_intel_kinds=missing_intel_kinds,
    )

    return report
