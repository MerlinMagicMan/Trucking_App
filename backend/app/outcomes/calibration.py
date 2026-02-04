"""
Prediction Calibration — Stratum 5A

Pure-function module: aggregates completed outcomes vs prediction snapshots
to measure systematic bias in the engine's predictions.

No caching, no side effects. Computed fresh on every call.
All money arithmetic uses Decimal — no floats.
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.plan_outcome import PlanPredictionSnapshot, PlanOutcome

TWO_PLACES = Decimal("0.01")

# Metric definitions: (name, get_predicted, get_actual)
# Each returns Optional[Decimal] from the snapshot/outcome pair.

METRIC_WEIGHTS = {
    "revenue": Decimal("0.20"),
    "costs": Decimal("0.25"),
    "net_profit": Decimal("0.30"),
    "miles": Decimal("0.10"),
    "duration": Decimal("0.15"),
}


def _dec(val) -> Optional[Decimal]:
    """Safely convert to Decimal."""
    if val is None:
        return None
    return Decimal(str(val))


def _get_predicted(snap: PlanPredictionSnapshot, metric: str) -> Optional[Decimal]:
    """Extract predicted value for a metric from snapshot."""
    if metric == "revenue":
        return _dec(snap.predicted_revenue)
    elif metric == "costs":
        return _dec(snap.predicted_costs)
    elif metric == "net_profit":
        return _dec(snap.predicted_net_profit)
    elif metric == "miles":
        return _dec(snap.predicted_miles_total)
    elif metric == "duration":
        return _dec(snap.predicted_duration_min)
    return None


def _get_actual(outcome: PlanOutcome, metric: str) -> Optional[Decimal]:
    """Extract actual value for a metric from outcome."""
    if metric == "revenue":
        return _dec(outcome.actual_revenue)
    elif metric == "costs":
        parts = [
            _dec(outcome.actual_fuel_spend),
            _dec(outcome.actual_tolls),
            _dec(outcome.actual_maintenance),
            _dec(outcome.actual_other_costs),
        ]
        if all(p is None for p in parts):
            return None
        return sum((p for p in parts if p is not None), Decimal("0"))
    elif metric == "net_profit":
        rev = _dec(outcome.actual_revenue)
        costs_parts = [
            _dec(outcome.actual_fuel_spend),
            _dec(outcome.actual_tolls),
            _dec(outcome.actual_maintenance),
            _dec(outcome.actual_other_costs),
        ]
        if rev is None or all(p is None for p in costs_parts):
            return None
        total_costs = sum((p for p in costs_parts if p is not None), Decimal("0"))
        return rev - total_costs
    elif metric == "miles":
        loaded = _dec(outcome.actual_miles_loaded)
        dh = _dec(outcome.actual_miles_deadhead)
        if loaded is None and dh is None:
            return None
        return (loaded or Decimal("0")) + (dh or Decimal("0"))
    elif metric == "duration":
        drive = _dec(outcome.actual_drive_min)
        wait = _dec(outcome.actual_wait_min)
        if drive is None and wait is None:
            return None
        return (drive or Decimal("0")) + (wait or Decimal("0"))
    return None


def _variance_pct(predicted: Decimal, actual: Decimal) -> Optional[Decimal]:
    """Signed variance percentage: (actual - predicted) / predicted * 100."""
    if predicted == 0:
        return None
    return ((actual - predicted) / abs(predicted) * Decimal("100")).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )


def _compute_metric(
    pairs: List[Tuple[Decimal, Decimal]],
    metric_name: str,
) -> Optional[Dict]:
    """Compute calibration stats for a single metric from (predicted, actual) pairs.

    Returns dict with keys matching CalibrationMetric schema, or None if no valid pairs.
    """
    if not pairs:
        return None

    n = len(pairs)
    errors = [actual - predicted for predicted, actual in pairs]
    abs_errors = [abs(e) for e in errors]
    variances = []
    for predicted, actual in pairs:
        v = _variance_pct(predicted, actual)
        if v is not None:
            variances.append(v)

    mean_error = (sum(errors) / n).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    mae = (sum(abs_errors) / n).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    predicted_avg = (sum(p for p, _ in pairs) / n).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    actual_avg = (sum(a for _, a in pairs) / n).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    if variances:
        mean_var_pct = (sum(variances) / len(variances)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
        worst_case = max(abs(v) for v in variances).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    else:
        mean_var_pct = Decimal("0.00")
        worst_case = Decimal("0.00")

    # Direction
    if abs(mean_var_pct) <= Decimal("2"):
        direction = "accurate"
    elif mean_error > 0:
        direction = "under"  # actual > predicted → engine under-predicted
    else:
        direction = "over"  # actual < predicted → engine over-predicted

    return {
        "name": metric_name,
        "predicted_avg": str(predicted_avg),
        "actual_avg": str(actual_avg),
        "mean_error": str(mean_error),
        "mae": str(mae),
        "mean_variance_pct": str(mean_var_pct),
        "direction": direction,
        "sample_size": n,
        "worst_case_pct": str(worst_case),
    }


def _generate_insights(
    metrics: List[Dict],
    accuracy_score: Decimal,
) -> List[str]:
    """Generate deterministic, rule-based insights. Always >= 3."""
    insights: List[str] = []

    for m in metrics:
        var = Decimal(m["mean_variance_pct"])
        if abs(var) > Decimal("10"):
            direction_word = "under-predicted" if var > 0 else "over-predicted"
            insights.append(
                f"{m['name'].replace('_', ' ').title()} is systematically "
                f"{direction_word} by {abs(var)}%"
            )

    if accuracy_score >= Decimal("80"):
        insights.append("Overall predictions are well-calibrated")
    elif accuracy_score < Decimal("60"):
        insights.append(
            "Predictions need recalibration — consider adjusting cost model"
        )
    else:
        insights.append("Predictions are moderately calibrated — room for improvement")

    # Ensure >= 3 insights
    if len(insights) < 3:
        # Add metric-specific observations
        for m in metrics:
            if len(insights) >= 3:
                break
            var = Decimal(m["mean_variance_pct"])
            if abs(var) <= Decimal("10") and m["direction"] != "accurate":
                insights.append(
                    f"{m['name'].replace('_', ' ').title()} shows minor "
                    f"{m['direction']}-prediction bias ({m['mean_variance_pct']}%)"
                )
    if len(insights) < 3:
        for m in metrics:
            if len(insights) >= 3:
                break
            if m["direction"] == "accurate":
                insights.append(
                    f"{m['name'].replace('_', ' ').title()} predictions are accurate "
                    f"(sample size: {m['sample_size']})"
                )
    while len(insights) < 3:
        insights.append(
            f"Calibration based on {metrics[0]['sample_size'] if metrics else 0} completed outcomes"
        )

    return insights


def compute_calibration_report(
    db: Session,
    org_id: str,
    window_days: int = 30,
    min_sample: int = 3,
) -> Optional[Dict]:
    """Compute calibration report for an org.

    Returns dict matching CalibrationReport schema, or None if insufficient data.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    # Query completed outcomes within window
    outcomes = (
        db.query(PlanOutcome)
        .filter(
            PlanOutcome.org_id == org_id,
            PlanOutcome.status == "complete",
            PlanOutcome.completed_at >= cutoff,
        )
        .all()
    )

    if len(outcomes) < min_sample:
        return None

    # Load linked snapshots
    snapshot_ids = {o.prediction_snapshot_id for o in outcomes if o.prediction_snapshot_id}
    snapshots_by_id = {}
    if snapshot_ids:
        snaps = (
            db.query(PlanPredictionSnapshot)
            .filter(PlanPredictionSnapshot.id.in_(snapshot_ids))
            .all()
        )
        snapshots_by_id = {str(s.id): s for s in snaps}

    # For outcomes without linked snapshot, try by plan_id
    for outcome in outcomes:
        sid = str(outcome.prediction_snapshot_id) if outcome.prediction_snapshot_id else None
        if sid and sid in snapshots_by_id:
            continue
        snap = (
            db.query(PlanPredictionSnapshot)
            .filter(
                PlanPredictionSnapshot.org_id == org_id,
                PlanPredictionSnapshot.plan_id == outcome.plan_id,
            )
            .order_by(PlanPredictionSnapshot.created_at.desc())
            .first()
        )
        if snap:
            snapshots_by_id[str(snap.id)] = snap

    # Build (predicted, actual) pairs per metric
    metric_pairs: Dict[str, List[Tuple[Decimal, Decimal]]] = {
        name: [] for name in METRIC_WEIGHTS
    }

    for outcome in outcomes:
        sid = str(outcome.prediction_snapshot_id) if outcome.prediction_snapshot_id else None
        snap = snapshots_by_id.get(sid) if sid else None
        if not snap:
            # Try by plan_id
            for s in snapshots_by_id.values():
                if s.plan_id == outcome.plan_id and str(s.org_id) == org_id:
                    snap = s
                    break
        if not snap:
            continue

        for metric_name in METRIC_WEIGHTS:
            predicted = _get_predicted(snap, metric_name)
            actual = _get_actual(outcome, metric_name)
            if predicted is not None and actual is not None:
                metric_pairs[metric_name].append((predicted, actual))

    # Compute per-metric stats
    metrics = []
    for metric_name in METRIC_WEIGHTS:
        pairs = metric_pairs[metric_name]
        if not pairs:
            continue
        result = _compute_metric(pairs, metric_name)
        if result:
            metrics.append(result)

    if not metrics:
        return None

    # Accuracy score: weighted average of per-metric scores
    # per_metric_score = max(0, 100 - abs(mean_variance_pct) * 4)
    weighted_sum = Decimal("0")
    weight_total = Decimal("0")
    for m in metrics:
        w = METRIC_WEIGHTS.get(m["name"], Decimal("0.10"))
        score = max(Decimal("0"), Decimal("100") - abs(Decimal(m["mean_variance_pct"])) * Decimal("4"))
        weighted_sum += score * w
        weight_total += w

    accuracy_score = (weighted_sum / weight_total).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    ) if weight_total > 0 else Decimal("0.00")

    insights = _generate_insights(metrics, accuracy_score)

    return {
        "org_id": org_id,
        "window_days": window_days,
        "computed_at": datetime.now(timezone.utc),
        "sample_size": len(outcomes),
        "accuracy_score": str(accuracy_score),
        "metrics": metrics,
        "insights": insights,
    }
