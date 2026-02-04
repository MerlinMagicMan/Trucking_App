"""
Decision endpoints — Stratum 4B: Decision Feedback Loop + Stratum 5D: Learning Loop

Endpoints:
  POST /decisions — record accept/reject/modify + auto-create snapshot+outcome on accept
  GET  /decisions?plan_id=X — list decisions for a plan (newest first)

On accept:
  - Creates PredictionSnapshot (immutable economics baseline)
  - Creates PlanOutcome (status=pending, ready for actuals)
  - Creates DecisionContextSnapshot (trust + copilot state at decision time)
"""
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.api.dependencies import get_org_id
from app.models.events import DecisionEvent, PlanGenerationEvent
from app.models.plan_outcome import PlanPredictionSnapshot, PlanOutcome
from app.models.decision_context import DecisionContextSnapshot
from app.outcomes.snapshotting import ensure_snapshot_for_plan
from app.copilot.schemas import DecisionCreate, DecisionResponse
from app.copilot.repository import find_plan_event, find_plan_by_id, check_load_active
from app.copilot.evaluator import evaluate_plan
from app.api.trust_routes import build_trust_report_for_plan
from app.calibration.profile import build_calibration_profile, CAL_WINDOW_DAYS_DEFAULT

logger = logging.getLogger(__name__)

decision_router = APIRouter(tags=["decisions"])


def _build_response(
    event: DecisionEvent,
    outcome_id: str = None,
    snapshot_id: str = None,
    decision_context_snapshot_id: str = None,
) -> dict:
    return {
        "id": event.id,
        "org_id": str(event.org_id),
        "plan_id": str(event.plan_id),
        "decision_type": event.decision_type,
        "reason": event.reason,
        "outcome_id": outcome_id,
        "prediction_snapshot_id": snapshot_id,
        "decision_context_snapshot_id": decision_context_snapshot_id,
        "timestamp": event.timestamp,
    }


def _capture_decision_context(
    db: Session,
    org_id: str,
    plan_id: str,
    decision_event_id: int,
) -> Optional[DecisionContextSnapshot]:
    """
    Capture trust + copilot state at decision time.

    Best-effort: never fails the decision if context capture fails.
    Returns DecisionContextSnapshot or None.
    """
    try:
        # Find plan
        plan = find_plan_by_id(db, org_id, plan_id)
        if not plan:
            return None

        # Extract plan economics (use calibrated if available)
        estimates = plan.get("estimates_calibrated") or plan.get("estimates_raw") or {}
        plan_revenue = Decimal(str(estimates.get("revenue", "0"))) if estimates.get("revenue") else None
        plan_costs = Decimal(str(estimates.get("costs", "0"))) if estimates.get("costs") else None
        plan_net_profit = Decimal(str(estimates.get("net_profit", "0"))) if estimates.get("net_profit") else None
        plan_duration = int(estimates.get("duration_min", 0)) if estimates.get("duration_min") else None
        plan_num_loads = len(plan.get("loads", []))

        # Build trust report
        trust_report = None
        trust_score = None
        trust_label = None
        trust_warnings = None
        trust_explanations = None
        trust_meta = None

        try:
            trust_report = build_trust_report_for_plan(db, org_id, plan, window_days=30)
            trust_score = trust_report.confidence_score
            trust_label = trust_report.confidence_label
            trust_warnings = [w.model_dump(mode="json") for w in trust_report.warnings]
            trust_explanations = trust_report.explanations
            trust_meta = trust_report.meta.model_dump(mode="json")
        except Exception as e:
            logger.warning(f"Trust capture failed for decision context: {e}")

        # Run copilot evaluation (simplified — no intel fetch to keep fast)
        copilot_status = None
        copilot_signals = None
        copilot_suggestions = None
        copilot_explanations = None

        try:
            loads = plan.get("loads", [])
            loads_active = {}  # Skip load availability check for speed
            for lip in loads:
                ld = lip.get("load", lip)
                key = ld.get("id", "unknown")
                loads_active[key] = True  # Assume active at decision time

            status, signals, suggestions, explanations = evaluate_plan(
                plan=plan,
                lane_rate_p50=None,  # Skip intel for speed
                lane_rate_p75=None,
                lane_time_to_cover=None,
                lane_load_count=None,
                market_temperature=None,
                efficiency_score=None,
                loads_active=loads_active,
            )
            copilot_status = status
            copilot_signals = signals
            copilot_suggestions = suggestions
            copilot_explanations = explanations
        except Exception as e:
            logger.warning(f"Copilot capture failed for decision context: {e}")

        # Get calibration profile stats
        cal_sample_size = None
        cal_confidence = None
        cal_applied = plan.get("calibration_meta", {}).get("applied", False)

        try:
            cal_profile = build_calibration_profile(db, org_id, CAL_WINDOW_DAYS_DEFAULT)
            if cal_profile:
                cal_sample_size = cal_profile.sample_size
                cal_confidence = cal_profile.confidence
        except Exception as e:
            logger.warning(f"Calibration profile fetch failed: {e}")

        # Create snapshot
        snapshot = DecisionContextSnapshot(
            org_id=org_id,
            plan_id=plan_id,
            decision_event_id=decision_event_id,
            captured_at=datetime.now(timezone.utc),
            trust_confidence_score=trust_score,
            trust_confidence_label=trust_label,
            trust_warnings=trust_warnings,
            trust_explanations=trust_explanations,
            trust_meta=trust_meta,
            copilot_status=copilot_status,
            copilot_signals=copilot_signals,
            copilot_suggestions=copilot_suggestions,
            copilot_explanations=copilot_explanations,
            calibration_sample_size=cal_sample_size,
            calibration_profile_confidence=cal_confidence,
            calibration_applied="yes" if cal_applied else "no",
            plan_revenue=plan_revenue,
            plan_costs=plan_costs,
            plan_net_profit=plan_net_profit,
            plan_duration_min=plan_duration,
            plan_num_loads=plan_num_loads,
            full_context={
                "plan_id": plan_id,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "has_trust": trust_report is not None,
                "has_copilot": copilot_status is not None,
            },
        )
        db.add(snapshot)
        db.flush()
        return snapshot

    except Exception as e:
        logger.warning(f"Decision context capture failed: {e}")
        return None


def _get_existing_outcome_ids(db: Session, org_id: str, plan_id: str):
    """Return (outcome_id, snapshot_id, decision_context_id) if an outcome already exists."""
    outcome = (
        db.query(PlanOutcome)
        .filter(PlanOutcome.org_id == org_id, PlanOutcome.plan_id == plan_id)
        .first()
    )
    # Also check for existing decision context snapshot
    context_snapshot = (
        db.query(DecisionContextSnapshot)
        .filter(DecisionContextSnapshot.org_id == org_id, DecisionContextSnapshot.plan_id == plan_id)
        .order_by(DecisionContextSnapshot.captured_at.desc())
        .first()
    )
    context_id = str(context_snapshot.id) if context_snapshot else None

    if outcome:
        return (
            str(outcome.id),
            str(outcome.prediction_snapshot_id) if outcome.prediction_snapshot_id else None,
            context_id,
        )
    return None, None, context_id


@decision_router.post("/decisions", response_model=DecisionResponse)
def create_decision(
    body: DecisionCreate,
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """
    Record a plan decision. On acceptance, auto-create prediction snapshot + outcome.

    Spam prevention: if the last decision for this plan matches
    (same decision_type and same reason), return it instead of inserting.
    """
    # --- Spam prevention: check last decision for this plan ---
    last_decision = (
        db.query(DecisionEvent)
        .filter(
            DecisionEvent.org_id == org_id,
            DecisionEvent.plan_id == body.plan_id,
        )
        .order_by(DecisionEvent.timestamp.desc())
        .first()
    )
    if last_decision:
        same_type = last_decision.decision_type == body.decision_type
        same_reason = (last_decision.reason or "") == (body.reason or "")
        if same_type and same_reason:
            # Return existing decision + any existing outcome/context ids
            oid, sid, ctx_id = _get_existing_outcome_ids(db, org_id, body.plan_id)
            return _build_response(
                last_decision, outcome_id=oid, snapshot_id=sid, decision_context_snapshot_id=ctx_id
            )

    # --- Find plan generation event for snapshot_id (required by DecisionEvent) ---
    plan_result = find_plan_event(db, org_id, body.plan_id)
    if not plan_result:
        raise HTTPException(status_code=404, detail="Plan not found")
    _, gen_event = plan_result
    generation_snapshot_id = gen_event.snapshot_id

    # --- Create DecisionEvent ---
    decision = DecisionEvent(
        plan_id=body.plan_id,
        snapshot_id=generation_snapshot_id,
        decision_type=body.decision_type,
        reason=body.reason,
        full_context={
            "source": "decision_api",
            "decision_type": body.decision_type,
            "reason": body.reason,
            "plan_generation_event_id": gen_event.id,
        },
        org_id=org_id,
    )
    db.add(decision)
    db.flush()

    outcome_id = None
    snapshot_id = None
    decision_context_snapshot_id = None

    if body.decision_type == "accepted":
        # Ensure prediction snapshot exists (idempotent)
        try:
            snapshot = ensure_snapshot_for_plan(db, org_id, body.plan_id)
            snapshot_id = str(snapshot.id)
        except HTTPException:
            logger.warning(f"Could not create prediction snapshot for plan {body.plan_id}")

        # Ensure outcome exists (idempotent per org_id + plan_id)
        existing_outcome = (
            db.query(PlanOutcome)
            .filter(PlanOutcome.org_id == org_id, PlanOutcome.plan_id == body.plan_id)
            .first()
        )
        if existing_outcome:
            outcome_id = str(existing_outcome.id)
        else:
            outcome = PlanOutcome(
                org_id=org_id,
                plan_id=body.plan_id,
                prediction_snapshot_id=snapshot_id,
                status="pending",
                source="decision",
            )
            db.add(outcome)
            db.flush()
            outcome_id = str(outcome.id)

        # Capture decision context snapshot (Stratum 5D: Learning Loop)
        # Best-effort: never fails the decision if context capture fails
        context_snapshot = _capture_decision_context(db, org_id, body.plan_id, decision.id)
        if context_snapshot:
            decision_context_snapshot_id = str(context_snapshot.id)

    db.commit()
    db.refresh(decision)
    return _build_response(
        decision,
        outcome_id=outcome_id,
        snapshot_id=snapshot_id,
        decision_context_snapshot_id=decision_context_snapshot_id,
    )


@decision_router.get("/decisions", response_model=List[DecisionResponse])
def list_decisions(
    plan_id: str = Query(...),
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """List decisions for a plan, newest first."""
    decisions = (
        db.query(DecisionEvent)
        .filter(
            DecisionEvent.org_id == org_id,
            DecisionEvent.plan_id == plan_id,
        )
        .order_by(DecisionEvent.timestamp.desc())
        .all()
    )

    # Pre-fetch outcome ids for this plan
    oid, sid, ctx_id = _get_existing_outcome_ids(db, org_id, plan_id)

    return [
        _build_response(
            d,
            outcome_id=oid if d.decision_type == "accepted" else None,
            snapshot_id=sid if d.decision_type == "accepted" else None,
            decision_context_snapshot_id=ctx_id if d.decision_type == "accepted" else None,
        )
        for d in decisions
    ]
