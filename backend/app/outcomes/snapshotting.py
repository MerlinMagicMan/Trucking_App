"""
Snapshot extraction helpers — shared by outcome_routes and decision_routes.

Extracted to avoid circular imports and duplication.
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.plan_outcome import PlanPredictionSnapshot
from app.copilot.repository import find_plan_event

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")


def _dec(val) -> Optional[Decimal]:
    """Convert any numeric to Decimal, or return None."""
    if val is None:
        return None
    return Decimal(str(val)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _dec_str(val) -> Optional[str]:
    """Convert Decimal/numeric to string for JSON response, or None."""
    if val is None:
        return None
    return str(Decimal(str(val)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


def extract_prediction_from_plan(plan_dict: dict, event) -> dict:
    """
    Extract canonical prediction structure from stored plan summary.
    Deterministic — uses only stored payload, never recomputes.
    """
    economics = {
        "gross_revenue": _dec_str(plan_dict.get("total_revenue_usd")),
        "total_costs": _dec_str(plan_dict.get("total_costs_usd")),
        "net_profit": _dec_str(plan_dict.get("net_profit_usd")),
        "profit_per_day": _dec_str(plan_dict.get("profit_per_day_usd")),
    }

    loads = plan_dict.get("loads", [])
    num_loads = plan_dict.get("num_loads") or len(loads)

    miles_loaded = 0
    miles_deadhead = 0
    for load_in_plan in loads:
        load_data = load_in_plan.get("load", {})
        miles_loaded += int(load_data.get("miles", 0) or 0)
        miles_deadhead += int(load_in_plan.get("deadhead_miles", 0) or 0)

    structure = {
        "num_loads": num_loads,
        "miles_loaded": miles_loaded if loads else None,
        "miles_deadhead": miles_deadhead if loads else None,
        "total_miles": (miles_loaded + miles_deadhead) if loads else None,
    }

    time_blocks = plan_dict.get("time_blocks", [])
    duration_min = None
    drive_min = None
    wait_min = None
    if time_blocks:
        duration_min = sum(tb.get("duration_min", 0) for tb in time_blocks)
        drive_min = sum(
            tb.get("duration_min", 0) for tb in time_blocks
            if tb.get("block_type") in ("drive_loaded", "drive_empty")
        )
        wait_min = sum(
            tb.get("duration_min", 0) for tb in time_blocks
            if tb.get("block_type") == "waiting"
        )

    time_summary = {
        "duration_min": duration_min,
        "drive_min": drive_min,
        "wait_min": wait_min,
    }

    request_data = {}
    if event and event.full_payload:
        req = event.full_payload.get("request", {})
        request_data = {
            "planning_horizon_days": req.get("planning_horizon_days"),
            "radius_miles": req.get("radius_miles"),
        }

    return {
        "economics_summary": economics,
        "time_summary": time_summary,
        "structure_summary": structure,
        "assumptions": request_data,
    }


def create_snapshot_for_plan(db: Session, org_id: str, plan_id: str) -> PlanPredictionSnapshot:
    """Create an immutable prediction snapshot from a stored plan.

    Raises HTTPException(404) if the plan is not found.
    """
    result = find_plan_event(db, org_id, plan_id)
    if not result:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan_dict, event = result
    predicted = extract_prediction_from_plan(plan_dict, event)

    loads = plan_dict.get("loads", [])
    miles_loaded = sum(int(lp.get("load", {}).get("miles", 0) or 0) for lp in loads)
    miles_deadhead = sum(int(lp.get("deadhead_miles", 0) or 0) for lp in loads)

    time_blocks = plan_dict.get("time_blocks", [])
    duration_min = sum(tb.get("duration_min", 0) for tb in time_blocks) if time_blocks else None

    snapshot = PlanPredictionSnapshot(
        org_id=org_id,
        plan_id=plan_id,
        plan_generation_event_id=event.id,
        predicted_revenue=_dec(plan_dict.get("total_revenue_usd")),
        predicted_costs=_dec(plan_dict.get("total_costs_usd")),
        predicted_net_profit=_dec(plan_dict.get("net_profit_usd")),
        predicted_profit_per_day=_dec(plan_dict.get("profit_per_day_usd")),
        predicted_miles_total=(miles_loaded + miles_deadhead) if loads else None,
        predicted_miles_deadhead=miles_deadhead if loads else None,
        predicted_duration_min=duration_min,
        predicted_num_loads=plan_dict.get("num_loads") or len(loads),
        predicted=predicted,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def ensure_snapshot_for_plan(db: Session, org_id: str, plan_id: str) -> PlanPredictionSnapshot:
    """Get existing snapshot or create one. Idempotent per (org_id, plan_id)."""
    existing = (
        db.query(PlanPredictionSnapshot)
        .filter(
            PlanPredictionSnapshot.org_id == org_id,
            PlanPredictionSnapshot.plan_id == plan_id,
        )
        .order_by(PlanPredictionSnapshot.created_at.desc())
        .first()
    )
    if existing:
        return existing
    return create_snapshot_for_plan(db, org_id, plan_id)
