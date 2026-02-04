"""
Tests for Risk Engine — Stratum 5D: Learning Loop

Covers: warning correlation, accuracy scoring, summary building, explanations.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone

from app.risk.engine import (
    dec,
    dec_str,
    correlate_single_warning,
    correlate_warnings_to_variance,
    compute_accuracy_score,
    label_accuracy,
    build_decision_context_summary,
    build_outcome_summary,
    build_explanations,
    build_risk_outcome_report,
)


# ---- Decimal helpers ----


class TestDecimalHelpers:
    def test_dec_none(self):
        assert dec(None) == Decimal("0")

    def test_dec_string(self):
        assert dec("123.45") == Decimal("123.45")

    def test_dec_str_none(self):
        assert dec_str(None) is None

    def test_dec_str_decimal(self):
        assert dec_str(Decimal("123.456")) == "123.46"


# ---- Single Warning Correlation ----


class TestCorrelateSingleWarning:
    def test_unverifiable_when_pending(self):
        warning = {
            "kind": "high_volatility",
            "severity": "medium",
            "title": "High volatility",
            "message": "Costs volatile",
        }
        variances = {"costs": Decimal("15")}
        result = correlate_single_warning(warning, variances, "pending")

        assert result.assessment == "unverifiable"
        assert result.outcome_verified is False

    def test_unverifiable_when_partial(self):
        warning = {
            "kind": "high_volatility",
            "severity": "medium",
            "title": "High volatility",
            "message": "Costs volatile",
        }
        variances = {"costs": Decimal("15")}
        result = correlate_single_warning(warning, variances, "partial")

        assert result.assessment == "unverifiable"

    def test_high_severity_correct_with_high_variance(self):
        """High severity warning + >20% variance = correct."""
        warning = {
            "kind": "high_volatility",
            "severity": "high",
            "title": "High volatility",
            "message": "Costs volatile",
        }
        variances = {"costs": Decimal("25"), "profit": Decimal("30")}
        result = correlate_single_warning(warning, variances, "complete")

        assert result.assessment == "correct"
        assert result.outcome_verified is True
        assert result.outcome_variance_pct is not None

    def test_high_severity_partially_correct_with_moderate_variance(self):
        """High severity warning + 10-20% variance = partially correct."""
        warning = {
            "kind": "high_volatility",
            "severity": "high",
            "title": "High volatility",
            "message": "Costs volatile",
        }
        variances = {"costs": Decimal("15"), "profit": Decimal("12")}
        result = correlate_single_warning(warning, variances, "complete")

        assert result.assessment == "partially_correct"

    def test_high_severity_false_alarm_with_low_variance(self):
        """High severity warning + <10% variance = false alarm."""
        warning = {
            "kind": "high_volatility",
            "severity": "high",
            "title": "High volatility",
            "message": "Costs volatile",
        }
        variances = {"costs": Decimal("5"), "profit": Decimal("3")}
        result = correlate_single_warning(warning, variances, "complete")

        assert result.assessment == "false_alarm"

    def test_medium_severity_correct_with_notable_variance(self):
        """Medium severity warning + >10% variance = correct."""
        warning = {
            "kind": "large_calibration_adjustment",
            "severity": "medium",
            "title": "Calibration adjustment",
            "message": "Adjusted by 15%",
        }
        variances = {"revenue": Decimal("18"), "costs": Decimal("5")}
        result = correlate_single_warning(warning, variances, "complete")

        assert result.assessment == "correct"

    def test_medium_severity_false_alarm_with_low_variance(self):
        """Medium severity warning + <10% variance = false alarm."""
        warning = {
            "kind": "large_calibration_adjustment",
            "severity": "medium",
            "title": "Calibration adjustment",
            "message": "Adjusted by 15%",
        }
        variances = {"revenue": Decimal("5"), "costs": Decimal("3")}
        result = correlate_single_warning(warning, variances, "complete")

        assert result.assessment == "false_alarm"

    def test_load_unavailable_unverifiable(self):
        """Load unavailable is always unverifiable (requires load tracking)."""
        warning = {
            "kind": "load_unavailable",
            "severity": "high",
            "title": "Load unavailable",
            "message": "Load may not be available",
        }
        variances = {"revenue": Decimal("50")}
        result = correlate_single_warning(warning, variances, "complete")

        assert result.assessment == "unverifiable"

    def test_no_relevant_variance_data(self):
        """Warning with no matching variance fields."""
        warning = {
            "kind": "high_volatility",
            "severity": "high",
            "title": "High volatility",
            "message": "Costs volatile",
        }
        variances = {}  # No data
        result = correlate_single_warning(warning, variances, "complete")

        assert result.assessment == "unverifiable"
        assert "No variance data" in result.assessment_explanation


# ---- Multiple Warning Correlation ----


class TestCorrelateWarningsToVariance:
    def test_empty_warnings(self):
        result = correlate_warnings_to_variance([], {"costs": Decimal("10")}, "complete")
        assert result == []

    def test_multiple_warnings(self):
        warnings = [
            {"kind": "high_volatility", "severity": "high", "title": "A", "message": "A"},
            {"kind": "low_sample_size", "severity": "medium", "title": "B", "message": "B"},
        ]
        variances = {"costs": Decimal("25"), "profit": Decimal("30")}
        result = correlate_warnings_to_variance(warnings, variances, "complete")

        assert len(result) == 2
        # All should be verifiable since complete
        for c in result:
            assert c.warning_kind in ("high_volatility", "low_sample_size")


# ---- Accuracy Score ----


class TestComputeAccuracyScore:
    def test_all_correct(self):
        correlations = [
            type("C", (), {"assessment": "correct", "warning_severity": "high"})(),
            type("C", (), {"assessment": "correct", "warning_severity": "medium"})(),
        ]
        score = compute_accuracy_score(correlations)
        assert score == 100

    def test_all_false_alarm(self):
        correlations = [
            type("C", (), {"assessment": "false_alarm", "warning_severity": "high"})(),
            type("C", (), {"assessment": "false_alarm", "warning_severity": "medium"})(),
        ]
        score = compute_accuracy_score(correlations)
        assert score == 0

    def test_mixed(self):
        correlations = [
            type("C", (), {"assessment": "correct", "warning_severity": "high"})(),  # 300
            type("C", (), {"assessment": "false_alarm", "warning_severity": "high"})(),  # 0
        ]
        # Total weight = 6, points = 300 → 50%
        score = compute_accuracy_score(correlations)
        assert score == 50

    def test_all_unverifiable_returns_50(self):
        correlations = [
            type("C", (), {"assessment": "unverifiable", "warning_severity": "high"})(),
        ]
        score = compute_accuracy_score(correlations)
        assert score == 50  # Neutral when no verifiable data

    def test_partially_correct(self):
        correlations = [
            type("C", (), {"assessment": "partially_correct", "warning_severity": "high"})(),
        ]
        score = compute_accuracy_score(correlations)
        assert score == 50


# ---- Accuracy Label ----


class TestLabelAccuracy:
    def test_insufficient_data_no_warnings(self):
        assert label_accuracy(80, has_warnings=False, has_outcome=True) == "insufficient_data"

    def test_insufficient_data_no_outcome(self):
        assert label_accuracy(80, has_warnings=True, has_outcome=False) == "insufficient_data"

    def test_accurate(self):
        assert label_accuracy(75, has_warnings=True, has_outcome=True) == "accurate"
        assert label_accuracy(100, has_warnings=True, has_outcome=True) == "accurate"

    def test_partially_accurate(self):
        assert label_accuracy(50, has_warnings=True, has_outcome=True) == "partially_accurate"
        assert label_accuracy(65, has_warnings=True, has_outcome=True) == "partially_accurate"

    def test_inaccurate(self):
        assert label_accuracy(30, has_warnings=True, has_outcome=True) == "inaccurate"
        assert label_accuracy(0, has_warnings=True, has_outcome=True) == "inaccurate"


# ---- Decision Context Summary ----


class TestBuildDecisionContextSummary:
    def test_none_returns_none(self):
        assert build_decision_context_summary(None) is None

    def test_builds_summary(self):
        context = {
            "captured_at": datetime.now(timezone.utc),
            "trust_confidence_score": 75,
            "trust_confidence_label": "medium",
            "trust_warnings": [{"kind": "a"}, {"kind": "b"}],
            "copilot_status": "degraded",
            "copilot_signals": [{"severity": "high"}, {"severity": "low"}],
            "calibration_sample_size": 25,
            "calibration_applied": "yes",
            "plan_revenue": Decimal("5000"),
            "plan_costs": Decimal("2500"),
            "plan_net_profit": Decimal("2500"),
        }
        result = build_decision_context_summary(context)

        assert result.trust_score == 75
        assert result.trust_label == "medium"
        assert result.trust_warning_count == 2
        assert result.copilot_status == "degraded"
        assert result.copilot_signal_count == 2
        assert result.copilot_high_severity_count == 1
        assert result.calibration_sample_size == 25


# ---- Outcome Summary ----


class TestBuildOutcomeSummary:
    def test_none_returns_none(self):
        assert build_outcome_summary(None, {}) is None

    def test_builds_summary(self):
        outcome = {
            "status": "complete",
            "completed_at": datetime.now(timezone.utc),
            "actual_revenue": Decimal("4800"),
            "actual_total_costs": Decimal("2700"),
            "actual_net_profit": Decimal("2100"),
        }
        variances = {
            "revenue": Decimal("-4"),
            "costs": Decimal("8"),
            "profit": Decimal("-16"),  # > 15%
        }
        result = build_outcome_summary(outcome, variances)

        assert result.status == "complete"
        assert result.actual_revenue == "4800.00"
        assert len(result.major_variance_fields) == 1
        assert "profit" in result.major_variance_fields


# ---- Explanations ----


class TestBuildExplanations:
    def test_minimum_3_explanations(self):
        explanations = build_explanations(
            context_summary=None,
            outcome_summary=None,
            correlations=[],
            accuracy_score=50,
            accuracy_label="insufficient_data",
        )
        assert len(explanations) >= 3

    def test_mentions_accuracy(self):
        explanations = build_explanations(
            context_summary=None,
            outcome_summary=None,
            correlations=[],
            accuracy_score=80,
            accuracy_label="accurate",
        )
        assert any("80%" in e for e in explanations)


# ---- Full Risk Outcome Report ----


class TestBuildRiskOutcomeReport:
    def test_no_context_no_outcome(self):
        report = build_risk_outcome_report(
            org_id="org-1",
            plan_id="plan-1",
            context_snapshot=None,
            outcome=None,
            variances={},
        )

        assert report.org_id == "org-1"
        assert report.plan_id == "plan-1"
        assert report.has_decision_context is False
        assert report.has_completed_outcome is False
        assert report.accuracy_assessment == "insufficient_data"
        assert len(report.explanations) >= 3

    def test_with_context_and_complete_outcome(self):
        context = {
            "captured_at": datetime.now(timezone.utc),
            "trust_confidence_score": 70,
            "trust_confidence_label": "medium",
            "trust_warnings": [
                {"kind": "high_volatility", "severity": "high", "title": "Vol", "message": "High"},
            ],
            "copilot_status": "degraded",
            "copilot_signals": [],
            "calibration_sample_size": 30,
            "calibration_applied": "yes",
            "plan_revenue": Decimal("5000"),
            "plan_costs": Decimal("2500"),
            "plan_net_profit": Decimal("2500"),
        }
        outcome = {
            "status": "complete",
            "completed_at": datetime.now(timezone.utc),
            "actual_revenue": Decimal("4800"),
            "actual_total_costs": Decimal("3000"),
            "actual_net_profit": Decimal("1800"),
        }
        variances = {
            "revenue": Decimal("-4"),
            "costs": Decimal("20"),
            "profit": Decimal("-28"),
        }

        report = build_risk_outcome_report(
            org_id="org-1",
            plan_id="plan-1",
            context_snapshot=context,
            outcome=outcome,
            variances=variances,
        )

        assert report.has_decision_context is True
        assert report.has_completed_outcome is True
        assert len(report.warning_correlations) == 1
        # High volatility warning should be correct with 28% profit variance
        assert report.warning_correlations[0].assessment == "correct"
        assert report.accuracy_score == 100

    def test_determinism(self):
        """Same inputs should produce same outputs."""
        context = {
            "captured_at": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "trust_confidence_score": 60,
            "trust_confidence_label": "medium",
            "trust_warnings": [
                {"kind": "low_sample_size", "severity": "medium", "title": "Low sample", "message": "Only 15"},
            ],
            "copilot_status": "ok",
            "copilot_signals": [],
        }
        outcome = {
            "status": "complete",
            "completed_at": datetime(2024, 1, 5, 12, 0, 0, tzinfo=timezone.utc),
            "actual_revenue": Decimal("5200"),
        }
        variances = {"revenue": Decimal("4"), "profit": Decimal("8")}

        report1 = build_risk_outcome_report("org", "plan", context, outcome, variances)
        report2 = build_risk_outcome_report("org", "plan", context, outcome, variances)

        assert report1.accuracy_score == report2.accuracy_score
        assert report1.accuracy_assessment == report2.accuracy_assessment
        assert len(report1.warning_correlations) == len(report2.warning_correlations)
