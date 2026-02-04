"""
Plan Outcome endpoints — Actuals vs Estimates (Phase 5, Stratum 4A + Stratum 5D)

Endpoints:
  POST /outcomes/prediction_snapshot — freeze prediction at acceptance
  POST /outcomes — create outcome record for actuals
  PATCH /outcomes/{outcome_id} — update actuals (partial)
  GET  /outcomes/report?plan_id=X — deterministic variance report
  GET  /outcomes/summary?limit=20 — recent outcomes with variance
  GET  /outcomes/risk_report?plan_id=X — risk outcome report (Stratum 5D)
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.api.dependencies import get_org_id
from app.models.plan_outcome import PlanPredictionSnapshot, PlanOutcome
from app.outcomes.snapshotting import (
    create_snapshot_for_plan,
    _dec,
    _dec_str,
)
from app.copilot.schemas import (
    PredictionSnapshotCreate,
    PredictionSnapshotResponse,
    OutcomeCreate,
    OutcomeUpdate,
    OutcomeResponse,
    OutcomeReport,
    VarianceDelta,
    OutcomeFlag,
    OutcomeSummaryItem,
)
from app.models.decision_context import DecisionContextSnapshot
from app.risk.schemas import RiskOutcomeReport
from app.risk.engine import build_risk_outcome_report

logger = logging.getLogger(__name__)

outcome_router = APIRouter(tags=["outcomes"])

TWO_PLACES = Decimal("0.01")


def _compute_variance_pct(predicted: Optional[Decimal], actual: Optional[Decimal]) -> Optional[Decimal]:
    """Deterministic variance percentage. Returns None if either value missing."""
    if predicted is None or actual is None:
        return None
    if predicted == 0:
        return Decimal("0.00")
    return ((actual - predicted) / abs(predicted) * 100).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )


def _snapshot_to_response(s: PlanPredictionSnapshot) -> dict:
    return {
        "id": str(s.id),
        "org_id": str(s.org_id),
        "plan_id": s.plan_id,
        "plan_generation_event_id": s.plan_generation_event_id,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "predicted_revenue": _dec_str(s.predicted_revenue),
        "predicted_costs": _dec_str(s.predicted_costs),
        "predicted_net_profit": _dec_str(s.predicted_net_profit),
        "predicted_profit_per_day": _dec_str(s.predicted_profit_per_day),
        "predicted_miles_total": s.predicted_miles_total,
        "predicted_miles_deadhead": s.predicted_miles_deadhead,
        "predicted_duration_min": s.predicted_duration_min,
        "predicted_num_loads": s.predicted_num_loads,
        "predicted": s.predicted or {},
    }


def _outcome_to_response(o: PlanOutcome) -> dict:
    return {
        "id": str(o.id),
        "org_id": str(o.org_id),
        "plan_id": o.plan_id,
        "prediction_snapshot_id": str(o.prediction_snapshot_id) if o.prediction_snapshot_id else None,
        "status": o.status,
        "source": o.source,
        "actual_revenue": _dec_str(o.actual_revenue),
        "actual_fuel_spend": _dec_str(o.actual_fuel_spend),
        "actual_tolls": _dec_str(o.actual_tolls),
        "actual_maintenance": _dec_str(o.actual_maintenance),
        "actual_other_costs": _dec_str(o.actual_other_costs),
        "actual_miles_loaded": o.actual_miles_loaded,
        "actual_miles_deadhead": o.actual_miles_deadhead,
        "actual_drive_min": o.actual_drive_min,
        "actual_wait_min": o.actual_wait_min,
        "actual": o.actual or {},
        "notes": o.notes,
        "recorded_at": o.recorded_at.isoformat() if o.recorded_at else None,
        "completed_at": o.completed_at.isoformat() if o.completed_at else None,
    }


# ---------- Endpoints ----------


@outcome_router.post("/outcomes/prediction_snapshot", response_model=PredictionSnapshotResponse)
def create_prediction_snapshot(
    body: PredictionSnapshotCreate,
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Freeze predicted economics at plan acceptance time. Immutable."""
    snapshot = create_snapshot_for_plan(db, org_id, body.plan_id)
    db.commit()
    db.refresh(snapshot)
    return _snapshot_to_response(snapshot)


@outcome_router.post("/outcomes", response_model=OutcomeResponse)
def create_outcome(
    body: OutcomeCreate,
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Create outcome record. Auto-creates prediction snapshot if not provided."""
    # Check for existing outcome
    existing = (
        db.query(PlanOutcome)
        .filter(PlanOutcome.org_id == org_id, PlanOutcome.plan_id == body.plan_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Outcome already exists for this plan")

    snapshot_id = None
    if body.prediction_snapshot_id:
        snapshot_id = body.prediction_snapshot_id
    else:
        # Auto-create snapshot
        try:
            snapshot = create_snapshot_for_plan(db, org_id, body.plan_id)
            snapshot_id = str(snapshot.id)
        except HTTPException:
            # Plan not found — create outcome without snapshot
            logger.warning(f"Could not create prediction snapshot for plan {body.plan_id}")

    outcome = PlanOutcome(
        org_id=org_id,
        plan_id=body.plan_id,
        prediction_snapshot_id=snapshot_id,
        status="pending",
        source="manual",
    )
    db.add(outcome)
    db.commit()
    db.refresh(outcome)
    return _outcome_to_response(outcome)


@outcome_router.patch("/outcomes/{outcome_id}", response_model=OutcomeResponse)
def update_outcome(
    outcome_id: str,
    body: OutcomeUpdate,
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Update outcome with actual results. Partial updates allowed."""
    outcome = (
        db.query(PlanOutcome)
        .filter(PlanOutcome.id == outcome_id, PlanOutcome.org_id == org_id)
        .first()
    )
    if not outcome:
        raise HTTPException(status_code=404, detail="Outcome not found")

    update_data = body.model_dump(exclude_unset=True)

    # Map string decimals to Numeric for money fields
    money_fields = ["actual_revenue", "actual_fuel_spend", "actual_tolls",
                    "actual_maintenance", "actual_other_costs"]
    for field in money_fields:
        if field in update_data and update_data[field] is not None:
            update_data[field] = _dec(update_data[field])

    for field, value in update_data.items():
        setattr(outcome, field, value)

    # Auto-detect status if not explicitly set
    if "status" not in update_data:
        required_for_complete = [outcome.actual_revenue, outcome.actual_fuel_spend]
        has_any = any(
            getattr(outcome, f) is not None
            for f in ["actual_revenue", "actual_fuel_spend", "actual_tolls",
                       "actual_miles_loaded", "actual_drive_min"]
        )
        has_required = all(v is not None for v in required_for_complete)
        if has_required:
            outcome.status = "complete"
            outcome.completed_at = datetime.utcnow()
        elif has_any:
            outcome.status = "partial"

    db.commit()
    db.refresh(outcome)
    return _outcome_to_response(outcome)


@outcome_router.get("/outcomes/report", response_model=OutcomeReport)
def get_outcome_report(
    plan_id: str = Query(...),
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """
    Deterministic variance report. Computes deltas and flags on read.
    Never caches variance — always recomputes from snapshot + outcome.
    """
    # Load latest snapshot
    snapshot = (
        db.query(PlanPredictionSnapshot)
        .filter(PlanPredictionSnapshot.org_id == org_id, PlanPredictionSnapshot.plan_id == plan_id)
        .order_by(PlanPredictionSnapshot.created_at.desc())
        .first()
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="No prediction snapshot found for this plan")

    # Load latest outcome
    outcome = (
        db.query(PlanOutcome)
        .filter(PlanOutcome.org_id == org_id, PlanOutcome.plan_id == plan_id)
        .order_by(PlanOutcome.recorded_at.desc())
        .first()
    )

    predicted_summary = snapshot.predicted or {}
    actual_summary = outcome.actual if outcome else {}

    # Compute deltas
    deltas = []
    flags = []
    explanations = []

    def _add_delta(field: str, pred_val, act_val, label: str):
        p = _dec(pred_val)
        a = _dec(act_val)
        var = _compute_variance_pct(p, a)
        deltas.append(VarianceDelta(
            field=field,
            predicted=_dec_str(p),
            actual=_dec_str(a),
            delta=_dec_str(a - p) if p is not None and a is not None else None,
            variance_pct=str(var) if var is not None else None,
        ))
        return p, a, var

    # Revenue
    p_rev, a_rev, v_rev = _add_delta(
        "revenue",
        snapshot.predicted_revenue,
        outcome.actual_revenue if outcome else None,
        "Revenue",
    )
    # Costs (predicted total costs vs sum of actual cost fields)
    actual_total_costs = None
    if outcome:
        cost_parts = [outcome.actual_fuel_spend, outcome.actual_tolls,
                      outcome.actual_maintenance, outcome.actual_other_costs]
        non_null = [_dec(c) for c in cost_parts if c is not None]
        if non_null:
            actual_total_costs = sum(non_null, Decimal("0"))
    p_cost, a_cost, v_cost = _add_delta(
        "total_costs", snapshot.predicted_costs, actual_total_costs, "Total Costs",
    )
    # Net profit
    actual_net = None
    if a_rev is not None and actual_total_costs is not None:
        actual_net = a_rev - actual_total_costs
    p_profit, a_profit, v_profit = _add_delta(
        "net_profit", snapshot.predicted_net_profit, actual_net, "Net Profit",
    )
    # Miles
    actual_total_miles = None
    if outcome and outcome.actual_miles_loaded is not None:
        actual_total_miles = (outcome.actual_miles_loaded or 0) + (outcome.actual_miles_deadhead or 0)
    _add_delta("total_miles", snapshot.predicted_miles_total, actual_total_miles, "Total Miles")
    # Duration
    actual_duration = None
    if outcome and outcome.actual_drive_min is not None:
        actual_duration = (outcome.actual_drive_min or 0) + (outcome.actual_wait_min or 0)
    p_dur, a_dur, v_dur = _add_delta(
        "duration_min", snapshot.predicted_duration_min, actual_duration, "Duration",
    )

    # Generate flags
    if v_cost is not None and v_cost > 10:
        sev = "high" if v_cost > 25 else "medium"
        flags.append(OutcomeFlag(
            flag="cost_overrun", severity=sev,
            summary=f"Costs exceeded prediction by {v_cost}%",
        ))
    if v_profit is not None and v_profit < -10:
        sev = "high" if v_profit < -25 else "medium"
        flags.append(OutcomeFlag(
            flag="profit_leakage", severity=sev,
            summary=f"Net profit was {abs(v_profit)}% below prediction",
        ))
    if v_rev is not None and v_rev < -10:
        sev = "high" if v_rev < -25 else "medium"
        flags.append(OutcomeFlag(
            flag="revenue_shortfall", severity=sev,
            summary=f"Revenue was {abs(v_rev)}% below prediction",
        ))
    if v_rev is not None and v_rev > 10:
        flags.append(OutcomeFlag(
            flag="revenue_surplus", severity="low",
            summary=f"Revenue exceeded prediction by {v_rev}%",
        ))
    if v_dur is not None and v_dur > 15:
        sev = "high" if v_dur > 30 else "medium"
        flags.append(OutcomeFlag(
            flag="time_overrun", severity=sev,
            summary=f"Duration exceeded prediction by {v_dur}%",
        ))

    # Generate explanations (≥3)
    if not outcome or outcome.status == "pending":
        explanations.append("No actuals recorded yet. Variance analysis will be available once actuals are entered.")
        explanations.append(f"Predicted net profit: ${_dec_str(snapshot.predicted_net_profit) or '—'}")
        explanations.append(f"Plan included {snapshot.predicted_num_loads or '?'} loads over {snapshot.predicted_miles_total or '?'} miles.")
    else:
        # Find largest variance driver
        numeric_deltas = [(d.field, d.variance_pct) for d in deltas if d.variance_pct is not None]
        numeric_deltas.sort(key=lambda x: abs(Decimal(x[1])), reverse=True)
        if numeric_deltas:
            top = numeric_deltas[0]
            explanations.append(f"Largest variance: {top[0]} at {top[1]}%.")
        if a_profit is not None and p_profit is not None:
            diff = a_profit - p_profit
            word = "above" if diff >= 0 else "below"
            explanations.append(f"Actual net profit was ${_dec_str(abs(diff))} {word} prediction.")
        explanations.append(f"Predicted: ${_dec_str(p_profit)} net profit on {snapshot.predicted_num_loads or '?'} loads.")
        if outcome.status == "partial":
            explanations.append("Some actuals still missing — final variance may change.")
        if len(explanations) < 3:
            explanations.append(f"Outcome status: {outcome.status}.")

    return OutcomeReport(
        plan_id=plan_id,
        prediction_snapshot_id=str(snapshot.id),
        outcome_id=str(outcome.id) if outcome else None,
        predicted_summary=predicted_summary,
        actual_summary=actual_summary,
        deltas=deltas,
        flags=flags,
        explanations=explanations,
    )


@outcome_router.get("/outcomes/summary", response_model=list)
def get_outcome_summary(
    limit: int = Query(20, ge=1, le=100),
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """List recent outcomes with deterministic variance computation."""
    outcomes = (
        db.query(PlanOutcome)
        .filter(PlanOutcome.org_id == org_id)
        .order_by(PlanOutcome.recorded_at.desc())
        .limit(limit)
        .all()
    )

    results = []
    for o in outcomes:
        # Load corresponding snapshot
        snapshot = (
            db.query(PlanPredictionSnapshot)
            .filter(
                PlanPredictionSnapshot.org_id == org_id,
                PlanPredictionSnapshot.plan_id == o.plan_id,
            )
            .order_by(PlanPredictionSnapshot.created_at.desc())
            .first()
        )

        # Compute variance deterministically
        profit_var = None
        time_var = None
        pred_net = None
        pred_dur = None
        if snapshot:
            pred_net = snapshot.predicted_net_profit
            pred_dur = snapshot.predicted_duration_min
            # Actual net profit = revenue - costs
            if o.actual_revenue is not None:
                cost_parts = [o.actual_fuel_spend, o.actual_tolls,
                              o.actual_maintenance, o.actual_other_costs]
                total_cost = sum((_dec(c) for c in cost_parts if c is not None), Decimal("0"))
                actual_net = _dec(o.actual_revenue) - total_cost
                profit_var = _compute_variance_pct(_dec(pred_net), actual_net)
            if o.actual_drive_min is not None and pred_dur is not None:
                actual_dur = (o.actual_drive_min or 0) + (o.actual_wait_min or 0)
                time_var = _compute_variance_pct(Decimal(str(pred_dur)), Decimal(str(actual_dur)))

        actual_net_str = None
        if o.actual_revenue is not None:
            cost_parts = [o.actual_fuel_spend, o.actual_tolls,
                          o.actual_maintenance, o.actual_other_costs]
            total_cost = sum((_dec(c) for c in cost_parts if c is not None), Decimal("0"))
            actual_net_str = _dec_str(_dec(o.actual_revenue) - total_cost)

        actual_dur = None
        if o.actual_drive_min is not None:
            actual_dur = (o.actual_drive_min or 0) + (o.actual_wait_min or 0)

        results.append({
            "plan_id": o.plan_id,
            "outcome_id": str(o.id),
            "status": o.status,
            "predicted_net_profit": _dec_str(pred_net) if pred_net else None,
            "actual_net_profit": actual_net_str,
            "profit_variance_pct": str(profit_var) if profit_var is not None else None,
            "predicted_duration_min": int(pred_dur) if pred_dur else None,
            "actual_duration_min": actual_dur,
            "time_variance_pct": str(time_var) if time_var is not None else None,
            "recorded_at": o.recorded_at.isoformat() if o.recorded_at else None,
            "completed_at": o.completed_at.isoformat() if o.completed_at else None,
        })
    return results


# ---- Stratum 5D: Risk Outcome Report ----


@outcome_router.get("/outcomes/risk_report", response_model=RiskOutcomeReport)
def get_risk_outcome_report(
    plan_id: str = Query(...),
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """
    Risk Outcome Report — Stratum 5D: Learning Loop

    Correlates pre-decision warnings to actual outcome variance.
    Shows "what we knew then" vs "what happened" for post-mortem analysis.

    Returns RiskOutcomeReport with:
      - decision_context: trust + copilot state at decision time
      - outcome_summary: actual results
      - warning_correlations: how well warnings predicted outcomes
      - accuracy_assessment: overall learning feedback
    """
    # 1. Load decision context snapshot (if exists)
    context_snapshot = (
        db.query(DecisionContextSnapshot)
        .filter(
            DecisionContextSnapshot.org_id == org_id,
            DecisionContextSnapshot.plan_id == plan_id,
        )
        .order_by(DecisionContextSnapshot.captured_at.desc())
        .first()
    )

    context_dict = None
    if context_snapshot:
        context_dict = {
            "captured_at": context_snapshot.captured_at,
            "trust_confidence_score": context_snapshot.trust_confidence_score,
            "trust_confidence_label": context_snapshot.trust_confidence_label,
            "trust_warnings": context_snapshot.trust_warnings or [],
            "trust_explanations": context_snapshot.trust_explanations,
            "trust_meta": context_snapshot.trust_meta,
            "copilot_status": context_snapshot.copilot_status,
            "copilot_signals": context_snapshot.copilot_signals or [],
            "copilot_suggestions": context_snapshot.copilot_suggestions,
            "calibration_sample_size": context_snapshot.calibration_sample_size,
            "calibration_applied": context_snapshot.calibration_applied,
            "plan_revenue": context_snapshot.plan_revenue,
            "plan_costs": context_snapshot.plan_costs,
            "plan_net_profit": context_snapshot.plan_net_profit,
        }

    # 2. Load outcome and prediction snapshot
    outcome = (
        db.query(PlanOutcome)
        .filter(PlanOutcome.org_id == org_id, PlanOutcome.plan_id == plan_id)
        .order_by(PlanOutcome.recorded_at.desc())
        .first()
    )

    snapshot = (
        db.query(PlanPredictionSnapshot)
        .filter(
            PlanPredictionSnapshot.org_id == org_id,
            PlanPredictionSnapshot.plan_id == plan_id,
        )
        .order_by(PlanPredictionSnapshot.created_at.desc())
        .first()
    )

    # 3. Build outcome dict
    outcome_dict = None
    if outcome:
        # Compute actual costs and net profit
        cost_parts = [
            outcome.actual_fuel_spend,
            outcome.actual_tolls,
            outcome.actual_maintenance,
            outcome.actual_other_costs,
        ]
        actual_total_costs = sum(
            (_dec(c) for c in cost_parts if c is not None), Decimal("0")
        )
        actual_net_profit = None
        if outcome.actual_revenue is not None:
            actual_net_profit = _dec(outcome.actual_revenue) - actual_total_costs

        outcome_dict = {
            "status": outcome.status,
            "completed_at": outcome.completed_at,
            "actual_revenue": outcome.actual_revenue,
            "actual_total_costs": actual_total_costs,
            "actual_net_profit": actual_net_profit,
        }

    # 4. Compute variances
    variances = {}
    if snapshot and outcome:
        # Revenue variance
        if outcome.actual_revenue is not None and snapshot.predicted_revenue is not None:
            variances["revenue"] = _compute_variance_pct(
                _dec(snapshot.predicted_revenue), _dec(outcome.actual_revenue)
            )

        # Costs variance
        if snapshot.predicted_costs is not None:
            variances["costs"] = _compute_variance_pct(
                _dec(snapshot.predicted_costs), actual_total_costs
            )

        # Profit variance
        if snapshot.predicted_net_profit is not None and actual_net_profit is not None:
            variances["profit"] = _compute_variance_pct(
                _dec(snapshot.predicted_net_profit), actual_net_profit
            )

        # Duration variance
        if (
            snapshot.predicted_duration_min is not None
            and outcome.actual_drive_min is not None
        ):
            actual_duration = (outcome.actual_drive_min or 0) + (outcome.actual_wait_min or 0)
            variances["duration"] = _compute_variance_pct(
                Decimal(str(snapshot.predicted_duration_min)),
                Decimal(str(actual_duration)),
            )

    # 5. Build risk outcome report using engine
    report = build_risk_outcome_report(
        org_id=org_id,
        plan_id=plan_id,
        context_snapshot=context_dict,
        outcome=outcome_dict,
        variances=variances,
    )

    return report
