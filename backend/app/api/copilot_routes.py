"""
Copilot API routes (Phase 4 + 4.1 + 4.2)

GET  /api/copilot/plan_status           — evaluate plan degradation
POST /api/copilot/branch_plans          — generate branch plans from suggestion
GET  /api/copilot/evaluations           — evaluation history for a plan
GET  /api/copilot/evaluations/{id}/replay — replay evaluation with current intel
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session

from app.api.dependencies import get_org_id
from app.db.connection import get_db

from app.copilot.schemas import (
    CopilotMeta, CopilotResponse,
    BranchPlanRequest, BranchPlanResponse, BranchPlanSummary,
    EvaluationHistoryItem, EvaluationReplayResponse, DriftSummary,
)
from app.copilot.repository import find_plan_by_id, find_plan_event, check_load_active
from app.copilot.evaluator import evaluate_plan, compute_drift
from app.intel.repository import (
    get_lane_statistic,
    get_market_statistic,
    get_destination_score,
)
from app.intel.time_windows import resolve_window
from app.models.copilot_evaluation import CopilotEvaluation
from app.models.canonical import TruckSnapshot, HOSSnapshot
from app.models.events import PlanGenerationEvent
from app.models.snapshot import LoadSnapshot
from app.engine.optimizer import OptimizationEngine
from app.engine.plan_generator import PlanGenerator
from app.engine.economics import EconomicsEngine
from app.connectors.truckstop import TruckstopConnector
from app.connectors.dat import DatConnector
from app.ingestion.snapshot_store import get_active_loads
from app.api.trust_routes import build_trust_report_for_plan

logger = logging.getLogger(__name__)

copilot_router = APIRouter(tags=["copilot"])

# Reuse the same engine instances as routes.py
_optimization_engine = OptimizationEngine(
    connectors=[TruckstopConnector(), DatConnector()]
)
_economics_engine = EconomicsEngine()
_plan_generator = PlanGenerator(_optimization_engine, _economics_engine)


# ---- Constraint mapping for branch plans ----

def _map_suggestion_to_constraints(
    suggestion_kind: str,
    suggestion_data: dict,
    original_horizon: int,
    original_radius: int,
    original_max_plans: int,
) -> dict:
    """Map a suggestion kind to constraint modifications. Returns dict of changed params."""
    changes = {}

    if suggestion_kind == "alternate_destination":
        new_radius = min(int(original_radius * 1.5), 500)
        changes["radius_miles"] = new_radius

    elif suggestion_kind == "add_buffer":
        new_horizon = max(original_horizon - 1, 7)
        changes["planning_horizon_days"] = new_horizon

    elif suggestion_kind == "take_now":
        changes["max_plans"] = 1

    # counter_offer: re-gen with same params (rate context in response)

    return changes


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

    # 5. Build trust report (never fail copilot if trust fails)
    missing_intel_kinds = []
    if not lane_stat:
        missing_intel_kinds.append("lane")
    if not market_stat:
        missing_intel_kinds.append("market")
    if not dest_score:
        missing_intel_kinds.append("destination")

    try:
        trust_report = build_trust_report_for_plan(
            db, org_id, plan,
            window_days=30,
            offline=base_meta.offline,
            missing_intel_kinds=missing_intel_kinds,
            copilot_signals=signals,
        )
        base_meta.trust = trust_report.model_dump(mode="json")

        # Confidence-aware suggestion reordering
        if trust_report.confidence_label == "medium":
            # Reorder suggestions: safer first
            safer_order = ["add_buffer", "alternate_destination", "counter_offer", "take_now", "manual_review"]
            suggestions = sorted(
                suggestions,
                key=lambda s: safer_order.index(s["kind"]) if s["kind"] in safer_order else 99
            )
            # Hedge rationale
            for sug in suggestions:
                if "based on" not in sug.get("rationale", "").lower():
                    sug["rationale"] = f"{sug.get('rationale', '')} (based on last 30 days of outcomes)"

        elif trust_report.confidence_label in ("low", "unknown"):
            # Add manual_review suggestion
            has_manual = any(s["kind"] == "manual_review" for s in suggestions)
            if not has_manual:
                suggestions.insert(0, {
                    "kind": "manual_review",
                    "summary": "Manual review recommended",
                    "rationale": f"Low confidence ({trust_report.confidence_score}/100) due to "
                                 + ("insufficient data" if trust_report.meta.sample_size < 10
                                    else "high prediction volatility"),
                    "data": {"confidence_score": trust_report.confidence_score},
                })

            # Suppress take_now unless conditions met
            take_now_allowed = (
                lane_stat
                and lane_stat.time_to_cover_p50_minutes is not None
                and lane_stat.time_to_cover_p50_minutes <= 60
                and lane_stat.rate_p50 is not None
            )
            if take_now_allowed and lane_stat:
                plan_rate = plan.get("loads", [{}])[0].get("load", {}).get("rate_total", 0)
                if lane_stat.rate_p50 < plan_rate * 1.1:
                    take_now_allowed = False

            if not take_now_allowed:
                original_len = len(suggestions)
                suggestions = [s for s in suggestions if s["kind"] != "take_now"]
                if len(suggestions) < original_len:
                    explanations.append("Take-now suppressed due to low confidence.")

    except Exception as exc:
        logger.warning("Trust report failed: %s", exc)
        base_meta.trust = None
        explanations.append("Trust evaluation unavailable.")

    # 6. Persist evaluation (best-effort)
    try:
        evaluation = CopilotEvaluation(
            org_id=org_id,
            plan_id=plan_id,
            status=status,
            signals=signals,
            suggestions=suggestions,
            explanations=explanations,
            meta=base_meta.model_dump(mode="json"),
        )
        db.add(evaluation)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to persist copilot evaluation: %s", exc)
        db.rollback()

    return CopilotResponse(
        meta=base_meta,
        status=status,
        signals=signals,
        suggestions=suggestions,
        explanations=explanations,
    )


@copilot_router.post("/copilot/branch_plans", response_model=BranchPlanResponse)
def branch_plans(
    req: BranchPlanRequest,
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Generate branch plans from a copilot suggestion."""

    # 1. Find parent plan + event
    result = find_plan_event(db, org_id, req.plan_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Plan {req.plan_id} not found.")

    _plan_dict, parent_event = result
    payload = parent_event.full_payload
    request_data = payload.get("request", {})

    # 2. Reconstruct TruckSnapshot from stored request
    hos_data = request_data.get("hos", {})
    try:
        snapshot = TruckSnapshot(
            snapshot_id=uuid4(),
            current_lat=request_data["current_lat"],
            current_lng=request_data["current_lng"],
            hos=HOSSnapshot(
                drive_remaining_min=hos_data.get("drive_remaining_min", 660),
                on_duty_remaining_min=hos_data.get("on_duty_remaining_min", 840),
                cycle_remaining_min=hos_data.get("cycle_remaining_min", 4200),
            ),
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not reconstruct truck state from parent plan: {exc}",
        )

    # 3. Map suggestion to constraint changes
    original_horizon = request_data.get("planning_horizon_days", 7)
    original_radius = request_data.get("radius_miles", 250)
    original_max = request_data.get("max_plans", 3)

    constraint_changes = _map_suggestion_to_constraints(
        req.suggestion_kind,
        req.suggestion_data,
        original_horizon,
        original_radius,
        original_max,
    )

    horizon = constraint_changes.get("planning_horizon_days", original_horizon)
    radius = constraint_changes.get("radius_miles", original_radius)
    max_plans = constraint_changes.get("max_plans", min(req.max_plans, 3))

    # 4. Check for preloaded snapshots
    preloaded = None
    snap_count = db.query(LoadSnapshot).filter(
        LoadSnapshot.org_id == org_id,
        LoadSnapshot.status == "active",
    ).count()
    if snap_count > 0:
        preloaded = get_active_loads(
            db, org_id,
            truck_lat=snapshot.current_lat,
            truck_lng=snapshot.current_lng,
            radius_miles=radius,
        )

    # 5. Generate branch plans
    try:
        plans = _plan_generator.generate_plans(
            snapshot,
            planning_horizon_days=horizon,
            max_plans=max_plans,
            radius_miles=radius,
            preloaded=preloaded,
        )
    except Exception as exc:
        logger.error("Branch plan generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Branch plan generation failed: {exc}")

    # 6. Store as PlanGenerationEvent with branch metadata
    branch_payload = {
        "request": {
            "snapshot_id": str(snapshot.snapshot_id),
            "timestamp": snapshot.timestamp.isoformat(),
            "current_lat": snapshot.current_lat,
            "current_lng": snapshot.current_lng,
            "hos": {
                "drive_remaining_min": snapshot.hos.drive_remaining_min,
                "on_duty_remaining_min": snapshot.hos.on_duty_remaining_min,
                "cycle_remaining_min": snapshot.hos.cycle_remaining_min,
            },
            "planning_horizon_days": horizon,
            "max_plans": max_plans,
            "radius_miles": radius,
            "branch_of": req.plan_id,
            "suggestion_kind": req.suggestion_kind,
        },
        "response": {
            "snapshot_id": str(snapshot.snapshot_id),
            "plans_generated": len(plans),
            "plans": [
                {
                    "plan_id": str(p.plan_id),
                    "num_loads": len(p.loads),
                    "profit_per_day_usd": p.profit_per_day_usd,
                    "net_profit_usd": p.net_profit_usd,
                    "total_revenue_usd": p.total_revenue_usd,
                    "total_costs_usd": p.total_costs_usd,
                    "end_location": p.end_location_name,
                    "confidence": p.confidence,
                    "plan_score": p.plan_score,
                    "load_ids": [ld.load.id for ld in p.loads],
                }
                for p in plans
            ],
            "warnings": [],
        },
    }

    try:
        event = PlanGenerationEvent(
            timestamp=datetime.utcnow(),
            snapshot_id=snapshot.snapshot_id,
            planning_horizon_days=horizon,
            plans_generated=len(plans),
            full_payload=branch_payload,
            org_id=org_id,
        )
        db.add(event)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to persist branch plan event: %s", exc)
        db.rollback()

    # 7. Build response
    summaries = [
        BranchPlanSummary(
            plan_id=str(p.plan_id),
            num_loads=len(p.loads),
            profit_per_day_usd=p.profit_per_day_usd,
            net_profit_usd=p.net_profit_usd,
            total_revenue_usd=p.total_revenue_usd,
            total_costs_usd=p.total_costs_usd,
            end_location=p.end_location_name,
            confidence=p.confidence,
            plan_score=p.plan_score,
        )
        for p in plans
    ]

    warnings = []
    if len(plans) == 0:
        warnings.append("No feasible branch plans found with modified constraints.")

    return BranchPlanResponse(
        parent_plan_id=req.plan_id,
        suggestion_applied=req.suggestion_kind,
        constraint_changes=constraint_changes,
        plans=summaries,
        warnings=warnings,
    )


# ---- Phase 4.2: Evaluation History + Replay ----


@copilot_router.get("/copilot/evaluations", response_model=List[EvaluationHistoryItem])
def list_evaluations(
    plan_id: str = Query(..., description="Plan ID to fetch evaluation history for"),
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """List copilot evaluations for a plan (newest first, limit 50)."""
    rows = (
        db.query(CopilotEvaluation)
        .filter(
            CopilotEvaluation.org_id == org_id,
            CopilotEvaluation.plan_id == plan_id,
        )
        .order_by(CopilotEvaluation.timestamp.desc())
        .limit(50)
        .all()
    )

    return [
        EvaluationHistoryItem(
            id=r.id,
            plan_id=r.plan_id,
            status=r.status,
            signal_count=len(r.signals) if r.signals else 0,
            suggestion_count=len(r.suggestions) if r.suggestions else 0,
            timestamp=r.timestamp,
            windows=r.meta.get("windows", {}) if r.meta else {},
            data_sources=r.meta.get("data_sources", {}) if r.meta else {},
        )
        for r in rows
    ]


@copilot_router.get("/copilot/evaluations/{eval_id}/replay", response_model=EvaluationReplayResponse)
def replay_evaluation(
    eval_id: int = Path(..., description="Evaluation ID to replay"),
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Replay a stored evaluation with current intel and show drift."""
    now = datetime.now(timezone.utc)

    # 1. Load stored evaluation
    stored = (
        db.query(CopilotEvaluation)
        .filter(CopilotEvaluation.id == eval_id, CopilotEvaluation.org_id == org_id)
        .first()
    )
    if stored is None:
        raise HTTPException(status_code=404, detail=f"Evaluation {eval_id} not found.")

    stored_meta = stored.meta or {}
    original_response = CopilotResponse(
        meta=CopilotMeta(
            org_id=str(stored.org_id),
            plan_id=stored.plan_id,
            as_of=stored_meta.get("as_of", stored.timestamp.isoformat()),
            evaluated_at=stored_meta.get("evaluated_at", stored.timestamp.isoformat()),
            windows=stored_meta.get("windows", {}),
            data_sources=stored_meta.get("data_sources", {}),
            offline=stored_meta.get("offline", False),
        ),
        status=stored.status,
        signals=stored.signals or [],
        suggestions=stored.suggestions or [],
        explanations=stored.explanations or [],
    )

    # 2. Find plan
    plan = find_plan_by_id(db, org_id, stored.plan_id)
    if plan is None:
        # Can't replay without plan — return original with empty replay
        empty_meta = CopilotMeta(
            org_id=str(org_id),
            plan_id=stored.plan_id,
            as_of=now,
            evaluated_at=now,
            windows={},
            data_sources={},
            offline=True,
        )
        return EvaluationReplayResponse(
            evaluation_id=eval_id,
            plan_id=stored.plan_id,
            original=original_response,
            replayed=CopilotResponse(
                meta=empty_meta,
                status="unknown",
                explanations=["Plan no longer found. Cannot replay."],
            ),
            drift=DriftSummary(),
            original_timestamp=stored.timestamp,
            replayed_at=now,
        )

    # 3. Re-run evaluation with current intel (same logic as plan_status)
    windows = stored_meta.get("windows", {"lane": "6h", "market": "6h", "destination": "24h"})
    replay_meta = CopilotMeta(
        org_id=str(org_id),
        plan_id=stored.plan_id,
        as_of=now,
        evaluated_at=now,
        windows=windows,
        data_sources={},
        offline=False,
    )

    loads = plan.get("loads", [])
    if not loads:
        replayed = CopilotResponse(
            meta=replay_meta, status="unknown", explanations=["Plan has no loads."],
        )
        return EvaluationReplayResponse(
            evaluation_id=eval_id,
            plan_id=stored.plan_id,
            original=original_response,
            replayed=replayed,
            drift=DriftSummary(),
            original_timestamp=stored.timestamp,
            replayed_at=now,
        )

    first_load = loads[0]
    load = first_load.get("load", first_load)
    origin_gh = load.get("pickup_geohash")
    dest_gh = load.get("delivery_geohash")

    if not origin_gh or not dest_gh:
        replayed = CopilotResponse(
            meta=replay_meta, status="unknown",
            explanations=["Plan loads missing geohash data."],
        )
        return EvaluationReplayResponse(
            evaluation_id=eval_id,
            plan_id=stored.plan_id,
            original=original_response,
            replayed=replayed,
            drift=DriftSummary(),
            original_timestamp=stored.timestamp,
            replayed_at=now,
        )

    # Fetch current intel
    lane_stat = None
    market_stat = None
    dest_score = None
    loads_active: dict = {}

    try:
        lane_start, lane_end, _ = resolve_window(windows.get("lane", "6h"))
        market_start, market_end, _ = resolve_window(windows.get("market", "6h"))
        dest_start, dest_end, _ = resolve_window(windows.get("destination", "24h"))

        lane_stat = get_lane_statistic(db, org_id, origin_gh, dest_gh, lane_start, lane_end)
        market_stat = get_market_statistic(db, org_id, dest_gh, market_start, market_end)
        dest_score = get_destination_score(db, org_id, dest_gh, dest_start, dest_end)

        for lip in loads:
            ld = lip.get("load", lip)
            source = ld.get("source", "")
            ext_id = ld.get("external_id", "")
            key = f"{source}/{ext_id}" if source and ext_id else ld.get("id", "unknown")
            if source and ext_id:
                loads_active[key] = check_load_active(db, org_id, source, ext_id)
            else:
                loads_active[key] = True
    except Exception as exc:
        logger.warning("Intel fetch failed during replay: %s", exc)
        replay_meta.offline = True
        replayed = CopilotResponse(
            meta=replay_meta, status="unknown",
            explanations=["Intel unavailable during replay."],
        )
        return EvaluationReplayResponse(
            evaluation_id=eval_id,
            plan_id=stored.plan_id,
            original=original_response,
            replayed=replayed,
            drift=DriftSummary(),
            original_timestamp=stored.timestamp,
            replayed_at=now,
        )

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

    replayed = CopilotResponse(
        meta=replay_meta,
        status=status,
        signals=signals,
        suggestions=suggestions,
        explanations=explanations,
    )

    # 5. Compute drift
    drift_raw = compute_drift(stored.signals or [], signals)
    drift = DriftSummary(**drift_raw)

    return EvaluationReplayResponse(
        evaluation_id=eval_id,
        plan_id=stored.plan_id,
        original=original_response,
        replayed=replayed,
        drift=drift,
        original_timestamp=stored.timestamp,
        replayed_at=now,
    )
