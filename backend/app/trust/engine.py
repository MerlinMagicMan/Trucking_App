"""
Trust Engine — Stratum 5C

Pure deterministic functions for computing trust scores and warnings.
NO DB access. Decimal-only numeric work.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Any

from app.trust.schemas import RiskWarning, ConfidenceLabel

TWO_PLACES = Decimal("0.01")


def dec(x) -> Decimal:
    """Safely convert to Decimal. Avoids float math."""
    if x is None:
        return Decimal("0")
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def quant2(d: Decimal) -> Decimal:
    """Quantize to 2 decimal places."""
    return d.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def compute_adjustment_pct(
    raw: Dict[str, str],
    calibrated: Dict[str, str],
) -> Dict[str, Decimal]:
    """Compute adjustment percentage for each metric.

    adjustment_pct = abs(cal - raw) / max(abs(raw), 1) * 100
    """
    result: Dict[str, Decimal] = {}
    metrics = ["revenue", "costs", "net_profit", "miles", "duration_min"]

    for metric in metrics:
        raw_val = dec(raw.get(metric, "0"))
        cal_val = dec(calibrated.get(metric, "0")) if calibrated else raw_val

        divisor = max(abs(raw_val), Decimal("1"))
        adj = abs(cal_val - raw_val) / divisor * Decimal("100")
        result[metric] = quant2(adj)

    return result


def compute_complexity_penalty(duration_min: Decimal, num_loads: int) -> Decimal:
    """Penalty based on plan duration and number of loads."""
    duration_hours = duration_min / Decimal("60")
    penalty = Decimal("0")

    if duration_hours >= Decimal("30"):
        penalty += Decimal("0.14")
    elif duration_hours >= Decimal("18"):
        penalty += Decimal("0.08")

    if num_loads >= 5:
        penalty += Decimal("0.12")
    elif num_loads >= 3:
        penalty += Decimal("0.06")

    return min(penalty, Decimal("0.25"))


def compute_offline_penalty(offline: bool, missing_intel_count: int) -> Decimal:
    """Penalty for offline mode or missing intel inputs."""
    if offline:
        return Decimal("0.25")
    return min(Decimal("0.18"), Decimal(str(missing_intel_count)) * Decimal("0.06"))


def compute_volatility_penalty(volatility_pct: Dict[str, str]) -> Decimal:
    """Penalty based on prediction volatility.

    Uses costs volatility as primary if present, else max volatility.
    """
    if not volatility_pct:
        return Decimal("0")

    costs_vol = dec(volatility_pct.get("costs", "0"))
    max_vol = max((dec(v) for v in volatility_pct.values()), default=Decimal("0"))
    primary_vol = costs_vol if costs_vol > Decimal("0") else max_vol

    penalty = Decimal("0")

    if primary_vol >= Decimal("35"):
        penalty = Decimal("0.22")
    elif primary_vol >= Decimal("20"):
        penalty = Decimal("0.10")

    # Extra penalty if 2+ metrics exceed 20%
    high_vol_count = sum(1 for v in volatility_pct.values() if dec(v) >= Decimal("20"))
    if high_vol_count >= 2:
        penalty += Decimal("0.05")

    return min(penalty, Decimal("0.30"))


def compute_adjustment_penalty(adjustment_pct: Dict[str, Decimal]) -> Decimal:
    """Penalty based on calibration adjustment magnitude."""
    if not adjustment_pct:
        return Decimal("0")

    # Use max of revenue/costs, or overall max
    revenue_adj = adjustment_pct.get("revenue", Decimal("0"))
    costs_adj = adjustment_pct.get("costs", Decimal("0"))
    primary_adj = max(revenue_adj, costs_adj)
    if primary_adj == Decimal("0"):
        primary_adj = max(adjustment_pct.values(), default=Decimal("0"))

    if primary_adj >= Decimal("20"):
        return Decimal("0.18")
    elif primary_adj >= Decimal("12"):
        return Decimal("0.10")

    return Decimal("0")


def compute_confidence_score(
    profile_confidence: Optional[Decimal],
    volatility_penalty: Decimal,
    adjustment_penalty: Decimal,
    complexity_penalty: Decimal,
    offline_penalty: Decimal,
) -> int:
    """Compute confidence score 0-100.

    If profile_confidence is None => 0 (unknown).
    """
    if profile_confidence is None:
        return 0

    total_penalty = volatility_penalty + adjustment_penalty + complexity_penalty + offline_penalty
    raw_score = Decimal("100") * (Decimal("1") - total_penalty) * profile_confidence

    # Clamp 0-100
    raw_score = max(Decimal("0"), min(Decimal("100"), raw_score))

    # Deterministic rounding
    return int((raw_score + Decimal("0.5")).quantize(Decimal("1")))


def label_confidence(score: int, offline: bool, sample_size: int) -> ConfidenceLabel:
    """Map score to confidence label."""
    if sample_size < 10:
        return "unknown"
    if offline and score < 55:
        return "unknown"
    if score >= 80:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def build_warnings(
    sample_size: int,
    profile_confidence: Optional[Decimal],
    volatility_pct: Dict[str, str],
    adjustment_pct: Dict[str, Decimal],
    offline: bool,
    missing_intel_kinds: List[str],
    plan_duration_min: Decimal,
    num_loads: int,
    copilot_signals: Optional[List[Dict[str, Any]]] = None,
    calibration_meta: Optional[Dict[str, Any]] = None,
) -> List[RiskWarning]:
    """Build deterministic list of risk warnings."""
    warnings: List[RiskWarning] = []

    # Sample size warnings
    if sample_size < 10:
        warnings.append(RiskWarning(
            kind="low_sample_size",
            severity="high",
            title="Insufficient data",
            message=f"Only {sample_size} completed outcomes. Need at least 10 for reliable calibration.",
            suggested_action="Complete more trips to improve prediction accuracy.",
        ))
    elif sample_size < 25:
        warnings.append(RiskWarning(
            kind="low_sample_size",
            severity="medium",
            title="Limited data",
            message=f"Only {sample_size} completed outcomes. Calibration improving.",
        ))

    # Confidence warnings
    if profile_confidence is not None:
        if profile_confidence < Decimal("0.45"):
            warnings.append(RiskWarning(
                kind="low_confidence",
                severity="high",
                title="Low prediction confidence",
                message=f"Calibration confidence is {quant2(profile_confidence * 100)}%. Historical predictions have been inconsistent.",
            ))
        elif profile_confidence < Decimal("0.60"):
            warnings.append(RiskWarning(
                kind="low_confidence",
                severity="medium",
                title="Moderate confidence",
                message=f"Calibration confidence is {quant2(profile_confidence * 100)}%.",
            ))

    # Volatility warnings
    costs_vol = dec(volatility_pct.get("costs", "0"))
    max_vol = max((dec(v) for v in volatility_pct.values()), default=Decimal("0"))
    primary_vol = costs_vol if costs_vol > Decimal("0") else max_vol

    if primary_vol >= Decimal("35"):
        warnings.append(RiskWarning(
            kind="high_volatility",
            severity="high",
            title="High prediction volatility",
            message=f"Cost predictions vary by {quant2(primary_vol)}%. Actual results may differ significantly.",
        ))
    elif primary_vol >= Decimal("20"):
        warnings.append(RiskWarning(
            kind="high_volatility",
            severity="medium",
            title="Moderate volatility",
            message=f"Cost predictions vary by {quant2(primary_vol)}%.",
        ))

    # Metric skipped by volatility (from calibration_meta)
    if calibration_meta:
        explanation = calibration_meta.get("explanation", [])
        for exp in explanation:
            if "skipped" in exp.lower() and "volatility" in exp.lower():
                warnings.append(RiskWarning(
                    kind="metric_skipped_by_volatility",
                    severity="medium",
                    title="Metric calibration skipped",
                    message=exp,
                ))
                break

    # Large calibration adjustment
    max_adj = max(adjustment_pct.values(), default=Decimal("0"))
    if max_adj >= Decimal("20"):
        warnings.append(RiskWarning(
            kind="large_calibration_adjustment",
            severity="high",
            title="Large calibration adjustment",
            message=f"Predictions adjusted by up to {quant2(max_adj)}% based on historical accuracy.",
            suggested_action="Review calibration report for details.",
        ))
    elif max_adj >= Decimal("12"):
        warnings.append(RiskWarning(
            kind="large_calibration_adjustment",
            severity="medium",
            title="Calibration adjustment applied",
            message=f"Predictions adjusted by up to {quant2(max_adj)}%.",
        ))

    # Offline warning
    if offline:
        warnings.append(RiskWarning(
            kind="offline_intel",
            severity="high",
            title="Intel offline",
            message="Market intelligence unavailable. Predictions may be stale.",
            suggested_action="Check network connection and retry.",
        ))

    # Missing intel
    if missing_intel_kinds:
        warnings.append(RiskWarning(
            kind="missing_intel_inputs",
            severity="medium",
            title="Incomplete market data",
            message=f"Missing: {', '.join(missing_intel_kinds)}.",
        ))

    # Duration/complexity warnings
    duration_hours = plan_duration_min / Decimal("60")
    if duration_hours >= Decimal("30"):
        warnings.append(RiskWarning(
            kind="long_horizon_uncertainty",
            severity="high",
            title="Long planning horizon",
            message=f"Plan spans {quant2(duration_hours)} hours. Market conditions may change.",
        ))
    elif duration_hours >= Decimal("18"):
        warnings.append(RiskWarning(
            kind="long_horizon_uncertainty",
            severity="medium",
            title="Extended timeline",
            message=f"Plan spans {quant2(duration_hours)} hours.",
        ))

    if num_loads >= 5:
        warnings.append(RiskWarning(
            kind="multi_load_complexity",
            severity="high",
            title="Complex multi-load plan",
            message=f"Plan includes {num_loads} loads. Execution complexity is high.",
        ))
    elif num_loads >= 3:
        warnings.append(RiskWarning(
            kind="multi_load_complexity",
            severity="medium",
            title="Multi-load plan",
            message=f"Plan includes {num_loads} loads.",
        ))

    # Copilot signal-derived warnings
    if copilot_signals:
        for signal in copilot_signals:
            kind = signal.get("kind", "")
            severity = signal.get("severity", "low")

            if kind == "market_temp_downgrade" and signal.get("details", {}).get("temperature") == "cold":
                warnings.append(RiskWarning(
                    kind="market_cold_risk",
                    severity="medium",
                    title="Cold market conditions",
                    message="Destination market is cold. Reload may take longer.",
                ))

            if kind == "lane_rate_shift" and severity == "high":
                warnings.append(RiskWarning(
                    kind="lane_rate_instability",
                    severity="high",
                    title="Lane rate unstable",
                    message="Significant rate shift detected on this lane.",
                ))

            if kind == "destination_score_drop":
                warnings.append(RiskWarning(
                    kind="destination_reload_risk",
                    severity=severity,
                    title="Destination reload risk",
                    message="Destination efficiency score is low.",
                ))

            if kind == "load_unavailable":
                warnings.append(RiskWarning(
                    kind="load_unavailable",
                    severity="high",
                    title="Load no longer available",
                    message="One or more loads in this plan may no longer be available.",
                    suggested_action="Regenerate plans now.",
                ))

    return warnings


def build_explanations(
    sample_size: int,
    window_days: int,
    profile_confidence: Optional[Decimal],
    volatility_penalty: Decimal,
    adjustment_penalty: Decimal,
    complexity_penalty: Decimal,
    offline_penalty: Decimal,
    confidence_score: int,
    confidence_label: ConfidenceLabel,
) -> List[str]:
    """Build at least 3 explanation strings."""
    explanations: List[str] = []

    # Base explanation
    explanations.append(
        f"Trust score {confidence_score}/100 ({confidence_label}) based on {sample_size} outcomes over {window_days} days."
    )

    # Penalty drivers
    penalties = []
    if volatility_penalty > Decimal("0"):
        penalties.append(f"volatility ({quant2(volatility_penalty * 100)}%)")
    if adjustment_penalty > Decimal("0"):
        penalties.append(f"calibration adjustment ({quant2(adjustment_penalty * 100)}%)")
    if complexity_penalty > Decimal("0"):
        penalties.append(f"plan complexity ({quant2(complexity_penalty * 100)}%)")
    if offline_penalty > Decimal("0"):
        penalties.append(f"offline/missing intel ({quant2(offline_penalty * 100)}%)")

    if penalties:
        explanations.append(f"Score reduced by: {', '.join(penalties)}.")
    else:
        explanations.append("No significant penalty factors detected.")

    # Confidence context
    if profile_confidence is not None:
        conf_pct = quant2(profile_confidence * 100)
        if profile_confidence >= Decimal("0.80"):
            explanations.append(f"Calibration confidence is strong at {conf_pct}%.")
        elif profile_confidence >= Decimal("0.60"):
            explanations.append(f"Calibration confidence is moderate at {conf_pct}%.")
        else:
            explanations.append(f"Calibration confidence is low at {conf_pct}%. More data will improve accuracy.")
    else:
        explanations.append("No calibration profile available. Trust score reflects baseline uncertainty.")

    # Ensure at least 3
    while len(explanations) < 3:
        explanations.append(f"Based on calibration window of {window_days} days.")

    return explanations
