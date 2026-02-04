"""
Calibration Application — Stratum 5B

Applies a CalibrationProfile to raw plan estimates.
No mutation of inputs. Decimal-only math.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

from app.calibration.schemas import CalibrationProfile, PlanEstimates, CalibrationAppliedMeta
from app.calibration.profile import (
    CAL_MIN_SAMPLE_SIZE,
    CAL_MIN_CONFIDENCE,
    CAL_BIAS_CAP,
    CAL_DISABLE_IF_VOLATILITY_GT,
)

TWO_PLACES = Decimal("0.01")
ONE_PLACE = Decimal("0.1")

# Config flag: when True, calibrated values are used for scoring
USE_CALIBRATED_SCORING = True


def clamp_bias(bias: Decimal, cap: Decimal = CAL_BIAS_CAP) -> Decimal:
    """Cap bias to ±cap. Returns clamped value."""
    if bias > cap:
        return cap
    if bias < -cap:
        return -cap
    return bias


def _is_eligible(profile: CalibrationProfile) -> tuple:
    """Check if profile meets eligibility criteria.

    Returns (eligible: bool, reasons: List[str], caps_applied: List[str]).
    """
    reasons: List[str] = []
    confidence = Decimal(profile.confidence)

    if profile.sample_size < CAL_MIN_SAMPLE_SIZE:
        reasons.append(
            f"Sample size {profile.sample_size} below minimum {CAL_MIN_SAMPLE_SIZE}"
        )

    if confidence < CAL_MIN_CONFIDENCE:
        reasons.append(
            f"Confidence {profile.confidence} below minimum {CAL_MIN_CONFIDENCE}"
        )

    # Per-metric volatility is checked during application (skip that metric only),
    # not at the profile level.

    return len(reasons) == 0, reasons


def apply_calibration_to_prediction(
    pred: Dict[str, Decimal],
    profile: CalibrationProfile,
) -> tuple:
    """Apply calibration adjustments to raw prediction values.

    Args:
        pred: Dict with keys: revenue, costs, net_profit, miles, duration, profit_per_day
              Values are Decimal.
        profile: CalibrationProfile with bias_pct_by_metric.

    Returns:
        (calibrated: Dict[str, Decimal], meta: CalibrationAppliedMeta)
    """
    eligible, ineligible_reasons = _is_eligible(profile)

    if not eligible:
        return dict(pred), CalibrationAppliedMeta(
            applied=False,
            window_days=profile.window_days,
            sample_size=profile.sample_size,
            confidence=profile.confidence,
            explanation=[
                "Calibration not applied",
                *ineligible_reasons,
            ],
        )

    calibrated = dict(pred)
    caps_applied: List[str] = []
    explanations: List[str] = [
        f"Calibration applied using {profile.sample_size} outcomes over {profile.window_days} days",
        f"Confidence: {profile.confidence}",
    ]

    # Apply per-metric bias adjustments
    # bias_pct is mean_variance_pct: (actual - predicted) / predicted * 100
    # To correct: multiply predicted by (1 + bias_pct/100)
    adjustment_metrics = ["revenue", "costs", "miles", "duration"]

    for metric in adjustment_metrics:
        bias_str = profile.bias_pct_by_metric.get(metric, "0.00")
        vol_str = profile.volatility_pct_by_metric.get(metric, "0.00")
        bias = Decimal(bias_str) / Decimal("100")
        vol = Decimal(vol_str)

        # Skip metric if volatility too high
        if vol > CAL_DISABLE_IF_VOLATILITY_GT:
            explanations.append(
                f"{metric}: skipped (volatility {vol_str}% > {CAL_DISABLE_IF_VOLATILITY_GT}%)"
            )
            continue

        # Skip if no meaningful bias
        if abs(bias) < Decimal("0.005"):
            continue

        # Clamp
        original_bias = bias
        bias = clamp_bias(bias)
        if bias != original_bias:
            caps_applied.append(metric)

        factor = Decimal("1") + bias
        raw_val = pred.get(metric, Decimal("0"))

        if metric in ("revenue", "costs"):
            calibrated[metric] = (raw_val * factor).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        elif metric == "miles":
            calibrated[metric] = (raw_val * factor).quantize(ONE_PLACE, rounding=ROUND_HALF_UP)
        elif metric == "duration":
            calibrated[metric] = (raw_val * factor).quantize(ONE_PLACE, rounding=ROUND_HALF_UP)

        direction = "up" if bias > 0 else "down"
        explanations.append(
            f"{metric}: adjusted {direction} by {abs(bias * Decimal('100')).quantize(TWO_PLACES)}%"
            + (f" (capped from {abs(original_bias * Decimal('100')).quantize(TWO_PLACES)}%)" if metric in caps_applied else "")
        )

    # Recompute net_profit from calibrated revenue and costs
    cal_revenue = calibrated.get("revenue", pred.get("revenue", Decimal("0")))
    cal_costs = calibrated.get("costs", pred.get("costs", Decimal("0")))
    calibrated["net_profit"] = (cal_revenue - cal_costs).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # Recompute profit_per_day if we have horizon info (passed via pred)
    if "profit_per_day" in pred and "planning_horizon_days" in pred:
        horizon = pred["planning_horizon_days"]
        if horizon > 0:
            calibrated["profit_per_day"] = (
                calibrated["net_profit"] / horizon
            ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    bias_pct_applied = {}
    for metric in adjustment_metrics:
        bias_str = profile.bias_pct_by_metric.get(metric, "0.00")
        bias = Decimal(bias_str) / Decimal("100")
        clamped = clamp_bias(bias)
        bias_pct_applied[metric] = str((clamped * Decimal("100")).quantize(TWO_PLACES))

    meta = CalibrationAppliedMeta(
        applied=True,
        window_days=profile.window_days,
        sample_size=profile.sample_size,
        confidence=profile.confidence,
        bias_pct_by_metric=bias_pct_applied,
        caps_applied=caps_applied if caps_applied else None,
        explanation=explanations,
    )

    return calibrated, meta


def build_plan_estimates(
    plan_revenue: Decimal,
    plan_costs: Decimal,
    plan_net_profit: Decimal,
    plan_profit_per_day: Decimal,
    plan_miles: Decimal,
    plan_duration_min: Decimal,
) -> PlanEstimates:
    """Build a PlanEstimates from plan values."""
    return PlanEstimates(
        revenue=str(plan_revenue.quantize(TWO_PLACES)),
        costs=str(plan_costs.quantize(TWO_PLACES)),
        net_profit=str(plan_net_profit.quantize(TWO_PLACES)),
        miles=str(plan_miles.quantize(ONE_PLACE)),
        duration_min=str(plan_duration_min.quantize(ONE_PLACE)),
        profit_per_day=str(plan_profit_per_day.quantize(TWO_PLACES)),
    )
