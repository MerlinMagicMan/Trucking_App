"""
Calibration Profile Builder — Stratum 5B

Pure computation: builds a CalibrationProfile from completed outcomes.
Decimal-only math. Minimal DB access.
"""
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.plan_outcome import PlanPredictionSnapshot, PlanOutcome
from app.calibration.schemas import CalibrationProfile

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")

# ---- Constants (single config) ----
CAL_WINDOW_DAYS_DEFAULT = 30
CAL_MIN_SAMPLE_SIZE = 10
CAL_MIN_CONFIDENCE = Decimal("0.60")
CAL_BIAS_CAP = Decimal("0.25")
CAL_DISABLE_IF_VOLATILITY_GT = Decimal("35")


# ---- Metric extraction (reuses logic from calibration.py) ----

def _dec(val) -> Optional[Decimal]:
    if val is None:
        return None
    return Decimal(str(val))


def _get_predicted(snap: PlanPredictionSnapshot, metric: str) -> Optional[Decimal]:
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


# ---- Confidence ----

METRICS = ["revenue", "costs", "net_profit", "miles", "duration"]


def compute_confidence(sample_size: int, volatility_pct: Decimal) -> Decimal:
    """Confidence in [0, 1]. Increases with sample size, decreases with volatility.

    Formula: confidence = sample_factor * volatility_factor
      sample_factor = min(1, sample_size / 50)  — saturates at 50
      volatility_factor = max(0, 1 - volatility_pct / 50)
    Monotonic, deterministic, explainable.
    """
    sample_factor = min(Decimal("1"), Decimal(str(sample_size)) / Decimal("50"))
    volatility_factor = max(
        Decimal("0"),
        Decimal("1") - volatility_pct / Decimal("50"),
    )
    return (sample_factor * volatility_factor).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def _compute_metric_stats(
    pairs: List[Tuple[Decimal, Decimal]],
) -> Tuple[Decimal, Decimal]:
    """Return (mean_variance_pct, volatility_pct) from (predicted, actual) pairs.

    mean_variance_pct = mean of (actual - predicted) / |predicted| * 100
    volatility_pct = standard deviation of per-sample variance_pct values
    """
    if not pairs:
        return Decimal("0"), Decimal("0")

    variances: List[Decimal] = []
    for predicted, actual in pairs:
        if predicted == 0:
            continue
        v = ((actual - predicted) / abs(predicted) * Decimal("100")).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP,
        )
        variances.append(v)

    if not variances:
        return Decimal("0"), Decimal("0")

    n = Decimal(str(len(variances)))
    mean_var = (sum(variances) / n).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # Standard deviation
    if len(variances) < 2:
        volatility = Decimal("0")
    else:
        sq_diffs = [(v - mean_var) ** 2 for v in variances]
        variance_of_var = sum(sq_diffs) / (n - Decimal("1"))
        # Integer sqrt approximation via Newton's method
        volatility = _decimal_sqrt(variance_of_var).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP,
        )

    return mean_var, volatility


def _decimal_sqrt(val: Decimal) -> Decimal:
    """Newton's method sqrt for Decimal."""
    if val <= 0:
        return Decimal("0")
    x = val
    for _ in range(50):
        x_new = (x + val / x) / Decimal("2")
        if abs(x_new - x) < Decimal("0.0001"):
            break
        x = x_new
    return x


def build_calibration_profile(
    db: Session,
    org_id: str,
    window_days: int = CAL_WINDOW_DAYS_DEFAULT,
) -> Optional[CalibrationProfile]:
    """Build a CalibrationProfile from completed outcomes.

    Returns None if fewer than CAL_MIN_SAMPLE_SIZE completed outcomes.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    outcomes = (
        db.query(PlanOutcome)
        .filter(
            PlanOutcome.org_id == org_id,
            PlanOutcome.status == "complete",
            PlanOutcome.completed_at >= cutoff,
        )
        .all()
    )

    if len(outcomes) < CAL_MIN_SAMPLE_SIZE:
        return None

    # Load snapshots
    snapshot_ids = {o.prediction_snapshot_id for o in outcomes if o.prediction_snapshot_id}
    snapshots_by_id: Dict[str, PlanPredictionSnapshot] = {}
    if snapshot_ids:
        snaps = (
            db.query(PlanPredictionSnapshot)
            .filter(PlanPredictionSnapshot.id.in_(snapshot_ids))
            .all()
        )
        snapshots_by_id = {str(s.id): s for s in snaps}

    # Fallback: by plan_id
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

    # Build pairs per metric
    metric_pairs: Dict[str, List[Tuple[Decimal, Decimal]]] = {m: [] for m in METRICS}

    for outcome in outcomes:
        sid = str(outcome.prediction_snapshot_id) if outcome.prediction_snapshot_id else None
        snap = snapshots_by_id.get(sid) if sid else None
        if not snap:
            for s in snapshots_by_id.values():
                if s.plan_id == outcome.plan_id and str(s.org_id) == org_id:
                    snap = s
                    break
        if not snap:
            continue

        for metric in METRICS:
            predicted = _get_predicted(snap, metric)
            actual = _get_actual(outcome, metric)
            if predicted is not None and actual is not None:
                metric_pairs[metric].append((predicted, actual))

    bias_pct: Dict[str, str] = {}
    volatility_pct: Dict[str, str] = {}
    max_volatility = Decimal("0")

    for metric in METRICS:
        pairs = metric_pairs[metric]
        if not pairs:
            bias_pct[metric] = "0.00"
            volatility_pct[metric] = "0.00"
            continue
        mean_var, vol = _compute_metric_stats(pairs)
        bias_pct[metric] = str(mean_var)
        volatility_pct[metric] = str(vol)
        if vol > max_volatility:
            max_volatility = vol

    confidence = compute_confidence(len(outcomes), max_volatility)

    return CalibrationProfile(
        org_id=org_id,
        window_days=window_days,
        sample_size=len(outcomes),
        bias_pct_by_metric=bias_pct,
        volatility_pct_by_metric=volatility_pct,
        confidence=str(confidence),
        generated_at=datetime.now(timezone.utc),
    )
