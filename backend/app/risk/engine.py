"""
Risk Engine — Stratum 5D: Learning Loop

Pure deterministic functions for correlating warnings to actual outcomes.
NO DB access. Decimal-only numeric work.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone

from app.risk.schemas import (
    WarningOutcomeCorrelation,
    DecisionContextSummary,
    OutcomeActualSummary,
    RiskOutcomeReport,
)

TWO_PLACES = Decimal("0.01")


def dec(x) -> Decimal:
    """Safely convert to Decimal. Avoids float math."""
    if x is None:
        return Decimal("0")
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def dec_str(d) -> Optional[str]:
    """Convert Decimal to 2-place string, or None."""
    if d is None:
        return None
    return str(dec(d).quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


# ---- Warning → Outcome Mapping ----

# Which variance field(s) each warning kind should be checked against
WARNING_TO_VARIANCE_FIELDS: Dict[str, List[str]] = {
    "low_sample_size": ["profit", "costs", "revenue"],  # General uncertainty
    "low_confidence": ["profit", "costs", "revenue"],  # General uncertainty
    "high_volatility": ["costs", "profit"],  # Volatility implies cost unpredictability
    "metric_skipped_by_volatility": ["costs", "profit"],
    "large_calibration_adjustment": ["revenue", "costs", "profit"],
    "offline_intel": ["revenue", "profit"],  # Stale data → rate/profit risk
    "missing_intel_inputs": ["revenue", "profit"],
    "long_horizon_uncertainty": ["costs", "duration", "profit"],  # Time = more variance
    "multi_load_complexity": ["duration", "costs", "profit"],  # Execution complexity
    "market_cold_risk": ["duration", "revenue"],  # Reload delays
    "lane_rate_instability": ["revenue", "profit"],  # Rate shifts
    "destination_reload_risk": ["duration", "revenue"],  # Reload difficulty
    "load_unavailable": [],  # This is binary: plan didn't execute as planned
}

# Variance thresholds for warning accuracy assessment
VARIANCE_THRESHOLD_MEDIUM = Decimal("10")  # >10% = notable variance
VARIANCE_THRESHOLD_HIGH = Decimal("20")  # >20% = significant variance


def correlate_single_warning(
    warning: Dict[str, Any],
    variances: Dict[str, Optional[Decimal]],
    outcome_status: str,
) -> WarningOutcomeCorrelation:
    """
    Correlate a single warning to actual outcome variances.

    Args:
        warning: RiskWarning dict with kind, severity, title, message
        variances: Dict of field → variance_pct (absolute, as Decimal)
        outcome_status: pending/partial/complete

    Returns:
        WarningOutcomeCorrelation with assessment
    """
    kind = warning.get("kind", "unknown")
    severity = warning.get("severity", "low")
    title = warning.get("title", "")
    message = warning.get("message", "")

    # Get relevant variance fields for this warning kind
    relevant_fields = WARNING_TO_VARIANCE_FIELDS.get(kind, [])

    # If outcome not complete, we can't verify
    if outcome_status != "complete":
        return WarningOutcomeCorrelation(
            warning_kind=kind,
            warning_severity=severity,
            warning_title=title,
            warning_message=message,
            outcome_verified=False,
            outcome_variance_field=None,
            outcome_variance_pct=None,
            assessment="unverifiable",
            assessment_explanation="Outcome not yet complete — cannot verify warning accuracy.",
        )

    # Special case: load_unavailable — this is about whether plan executed at all
    if kind == "load_unavailable":
        # We can't easily verify this without tracking which loads were actually hauled
        return WarningOutcomeCorrelation(
            warning_kind=kind,
            warning_severity=severity,
            warning_title=title,
            warning_message=message,
            outcome_verified=False,
            outcome_variance_field=None,
            outcome_variance_pct=None,
            assessment="unverifiable",
            assessment_explanation="Load availability requires comparing planned vs actual loads.",
        )

    # Find the highest variance among relevant fields
    max_variance: Optional[Decimal] = None
    max_field: Optional[str] = None
    for field in relevant_fields:
        var = variances.get(field)
        if var is not None:
            var_abs = abs(var)
            if max_variance is None or var_abs > max_variance:
                max_variance = var_abs
                max_field = field

    # No relevant variance data
    if max_variance is None:
        return WarningOutcomeCorrelation(
            warning_kind=kind,
            warning_severity=severity,
            warning_title=title,
            warning_message=message,
            outcome_verified=False,
            outcome_variance_field=None,
            outcome_variance_pct=None,
            assessment="unverifiable",
            assessment_explanation="No variance data available for relevant metrics.",
        )

    # Determine assessment based on warning severity vs actual variance
    if severity == "high":
        # High severity warning should predict >20% variance
        if max_variance >= VARIANCE_THRESHOLD_HIGH:
            assessment = "correct"
            explanation = f"High-severity warning correctly predicted significant variance ({max_field}: {max_variance}%)."
        elif max_variance >= VARIANCE_THRESHOLD_MEDIUM:
            assessment = "partially_correct"
            explanation = f"High-severity warning, moderate actual variance ({max_field}: {max_variance}%)."
        else:
            assessment = "false_alarm"
            explanation = f"High-severity warning, but actual variance was low ({max_field}: {max_variance}%)."
    elif severity == "medium":
        # Medium severity warning should predict >10% variance
        if max_variance >= VARIANCE_THRESHOLD_MEDIUM:
            assessment = "correct"
            explanation = f"Medium-severity warning correctly predicted notable variance ({max_field}: {max_variance}%)."
        else:
            assessment = "false_alarm"
            explanation = f"Medium-severity warning, but actual variance was minimal ({max_field}: {max_variance}%)."
    else:  # low or unknown severity
        # Low severity is informational, not predictive
        if max_variance >= VARIANCE_THRESHOLD_MEDIUM:
            assessment = "partially_correct"
            explanation = f"Low-severity warning, but outcome had notable variance ({max_field}: {max_variance}%)."
        else:
            assessment = "correct"
            explanation = f"Low-severity informational warning, outcome as expected."

    return WarningOutcomeCorrelation(
        warning_kind=kind,
        warning_severity=severity,
        warning_title=title,
        warning_message=message,
        outcome_verified=True,
        outcome_variance_field=max_field,
        outcome_variance_pct=dec_str(max_variance),
        assessment=assessment,
        assessment_explanation=explanation,
    )


def correlate_warnings_to_variance(
    warnings: List[Dict[str, Any]],
    variances: Dict[str, Optional[Decimal]],
    outcome_status: str,
) -> List[WarningOutcomeCorrelation]:
    """
    Correlate all warnings to actual outcome variances.

    Args:
        warnings: List of RiskWarning dicts
        variances: Dict of field → variance_pct (signed, as Decimal)
        outcome_status: pending/partial/complete

    Returns:
        List of WarningOutcomeCorrelation
    """
    correlations = []
    for warning in warnings:
        correlation = correlate_single_warning(warning, variances, outcome_status)
        correlations.append(correlation)
    return correlations


def compute_accuracy_score(correlations: List[WarningOutcomeCorrelation]) -> int:
    """
    Compute overall accuracy score 0-100 based on warning correlations.

    Scoring:
      - correct: +100
      - partially_correct: +50
      - false_alarm: +0
      - unverifiable: excluded from calculation

    Returns weighted average, or 50 if no verifiable warnings.
    """
    total_points = 0
    total_weight = 0

    for c in correlations:
        if c.assessment == "unverifiable":
            continue
        # Weight by severity
        weight = {"high": 3, "medium": 2, "low": 1}.get(c.warning_severity, 1)
        total_weight += weight
        if c.assessment == "correct":
            total_points += 100 * weight
        elif c.assessment == "partially_correct":
            total_points += 50 * weight
        # false_alarm adds 0

    if total_weight == 0:
        return 50  # Neutral when no verifiable data

    return int((Decimal(total_points) / Decimal(total_weight)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def label_accuracy(score: int, has_warnings: bool, has_outcome: bool) -> str:
    """Convert accuracy score to label."""
    if not has_warnings or not has_outcome:
        return "insufficient_data"
    if score >= 70:
        return "accurate"
    if score >= 40:
        return "partially_accurate"
    return "inaccurate"


def build_decision_context_summary(
    context_snapshot: Optional[Dict[str, Any]]
) -> Optional[DecisionContextSummary]:
    """Build summary from decision context snapshot dict."""
    if not context_snapshot:
        return None

    trust_warnings = context_snapshot.get("trust_warnings") or []
    copilot_signals = context_snapshot.get("copilot_signals") or []
    high_severity_count = sum(
        1 for s in copilot_signals if s.get("severity") == "high"
    )

    return DecisionContextSummary(
        captured_at=context_snapshot.get("captured_at") or datetime.now(timezone.utc),
        trust_score=context_snapshot.get("trust_confidence_score"),
        trust_label=context_snapshot.get("trust_confidence_label"),
        trust_warning_count=len(trust_warnings),
        copilot_status=context_snapshot.get("copilot_status"),
        copilot_signal_count=len(copilot_signals),
        copilot_high_severity_count=high_severity_count,
        calibration_sample_size=context_snapshot.get("calibration_sample_size"),
        calibration_applied=context_snapshot.get("calibration_applied"),
        plan_revenue=dec_str(context_snapshot.get("plan_revenue")),
        plan_costs=dec_str(context_snapshot.get("plan_costs")),
        plan_net_profit=dec_str(context_snapshot.get("plan_net_profit")),
    )


def build_outcome_summary(
    outcome: Optional[Dict[str, Any]],
    variances: Dict[str, Optional[Decimal]],
) -> Optional[OutcomeActualSummary]:
    """Build summary from outcome dict."""
    if not outcome:
        return None

    # Find major variance fields (>15%)
    major_fields = [
        field for field, var in variances.items()
        if var is not None and abs(var) > Decimal("15")
    ]

    return OutcomeActualSummary(
        status=outcome.get("status", "pending"),
        completed_at=outcome.get("completed_at"),
        actual_revenue=dec_str(outcome.get("actual_revenue")),
        actual_costs=dec_str(outcome.get("actual_total_costs")),
        actual_net_profit=dec_str(outcome.get("actual_net_profit")),
        revenue_variance_pct=dec_str(variances.get("revenue")),
        costs_variance_pct=dec_str(variances.get("costs")),
        profit_variance_pct=dec_str(variances.get("profit")),
        major_variance_fields=major_fields,
    )


def build_explanations(
    context_summary: Optional[DecisionContextSummary],
    outcome_summary: Optional[OutcomeActualSummary],
    correlations: List[WarningOutcomeCorrelation],
    accuracy_score: int,
    accuracy_label: str,
) -> List[str]:
    """Build at least 3 plain-English explanations."""
    explanations: List[str] = []

    # Accuracy headline
    if accuracy_label == "insufficient_data":
        explanations.append("Insufficient data to assess prediction accuracy — no completed outcome yet.")
    elif accuracy_label == "accurate":
        explanations.append(f"Warnings were {accuracy_score}% accurate — pre-decision alerts correctly predicted outcome variance.")
    elif accuracy_label == "partially_accurate":
        explanations.append(f"Warnings were partially accurate ({accuracy_score}%) — some alerts matched outcomes, others did not.")
    else:
        explanations.append(f"Warnings had low accuracy ({accuracy_score}%) — actual outcomes differed from predicted risks.")

    # Context summary
    if context_summary:
        if context_summary.trust_label:
            explanations.append(
                f"At decision time: trust was {context_summary.trust_label} ({context_summary.trust_score}/100) "
                f"with {context_summary.trust_warning_count} warnings."
            )
        if context_summary.copilot_status:
            explanations.append(
                f"Copilot status was '{context_summary.copilot_status}' with "
                f"{context_summary.copilot_high_severity_count} high-severity signals."
            )
    else:
        explanations.append("No decision context snapshot available — cannot show pre-decision state.")

    # Outcome summary
    if outcome_summary:
        if outcome_summary.status == "complete":
            if outcome_summary.major_variance_fields:
                explanations.append(
                    f"Significant variance (>15%) in: {', '.join(outcome_summary.major_variance_fields)}."
                )
            else:
                explanations.append("Actual results were within expected ranges — no major variances.")
        else:
            explanations.append(f"Outcome is {outcome_summary.status} — full variance analysis pending.")
    else:
        explanations.append("No outcome recorded yet for this plan.")

    # Warning correlation highlights
    correct_count = sum(1 for c in correlations if c.assessment == "correct")
    false_alarm_count = sum(1 for c in correlations if c.assessment == "false_alarm")
    if correct_count > 0:
        explanations.append(f"{correct_count} warning(s) correctly predicted variance.")
    if false_alarm_count > 0:
        explanations.append(f"{false_alarm_count} warning(s) were false alarms — flagged risk that didn't materialize.")

    # Ensure at least 3
    while len(explanations) < 3:
        explanations.append("Risk learning loop helps calibrate future warnings based on actual outcomes.")

    return explanations


def build_risk_outcome_report(
    org_id: str,
    plan_id: str,
    context_snapshot: Optional[Dict[str, Any]],
    outcome: Optional[Dict[str, Any]],
    variances: Dict[str, Optional[Decimal]],
) -> RiskOutcomeReport:
    """
    Build complete risk outcome report from context snapshot and outcome.

    This is the main entry point for the risk engine.
    All computation is deterministic and side-effect free.
    """
    # Build summaries
    context_summary = build_decision_context_summary(context_snapshot)
    outcome_summary = build_outcome_summary(outcome, variances)

    # Extract warnings from context snapshot
    pre_decision_warnings = (context_snapshot or {}).get("trust_warnings") or []
    outcome_status = (outcome or {}).get("status", "pending")

    # Correlate warnings to outcomes
    correlations = correlate_warnings_to_variance(
        pre_decision_warnings, variances, outcome_status
    )

    # Compute accuracy
    accuracy_score = compute_accuracy_score(correlations)
    has_warnings = len(pre_decision_warnings) > 0
    has_outcome = outcome is not None and outcome.get("status") == "complete"
    accuracy_label = label_accuracy(accuracy_score, has_warnings, has_outcome)

    # Build explanations
    explanations = build_explanations(
        context_summary, outcome_summary, correlations, accuracy_score, accuracy_label
    )

    return RiskOutcomeReport(
        org_id=org_id,
        plan_id=plan_id,
        computed_at=datetime.now(timezone.utc),
        decision_context=context_summary,
        pre_decision_warnings=pre_decision_warnings,
        outcome_summary=outcome_summary,
        warning_correlations=correlations,
        accuracy_assessment=accuracy_label,
        accuracy_score=accuracy_score,
        explanations=explanations,
        has_decision_context=context_snapshot is not None,
        has_completed_outcome=has_outcome,
    )
