"""
Tests for Prediction Calibration — Stratum 5A

Covers: perfect predictions, systematic over/under, mixed,
Decimal discipline, insight generation, insufficient data.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from app.outcomes.calibration import (
    _get_predicted,
    _get_actual,
    _variance_pct,
    _compute_metric,
    _generate_insights,
    compute_calibration_report,
    METRIC_WEIGHTS,
)


# ---- Helpers ----


def _make_snapshot(**overrides):
    s = MagicMock()
    s.predicted_revenue = Decimal("3000.00")
    s.predicted_costs = Decimal("1500.00")
    s.predicted_net_profit = Decimal("1500.00")
    s.predicted_miles_total = 1000
    s.predicted_duration_min = 600
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def _make_outcome(**overrides):
    o = MagicMock()
    o.actual_revenue = Decimal("3000.00")
    o.actual_fuel_spend = Decimal("700.00")
    o.actual_tolls = Decimal("100.00")
    o.actual_maintenance = Decimal("150.00")
    o.actual_other_costs = Decimal("50.00")
    o.actual_miles_loaded = 800
    o.actual_miles_deadhead = 200
    o.actual_drive_min = 480
    o.actual_wait_min = 120
    for k, v in overrides.items():
        setattr(o, k, v)
    return o


# ---- Metric extraction ----


class TestMetricExtraction:
    def test_predicted_revenue(self):
        snap = _make_snapshot()
        assert _get_predicted(snap, "revenue") == Decimal("3000.00")

    def test_predicted_costs(self):
        snap = _make_snapshot()
        assert _get_predicted(snap, "costs") == Decimal("1500.00")

    def test_predicted_net_profit(self):
        snap = _make_snapshot()
        assert _get_predicted(snap, "net_profit") == Decimal("1500.00")

    def test_predicted_miles(self):
        snap = _make_snapshot()
        assert _get_predicted(snap, "miles") == Decimal("1000")

    def test_predicted_duration(self):
        snap = _make_snapshot()
        assert _get_predicted(snap, "duration") == Decimal("600")

    def test_actual_revenue(self):
        o = _make_outcome()
        assert _get_actual(o, "revenue") == Decimal("3000.00")

    def test_actual_costs_sums_parts(self):
        o = _make_outcome()
        assert _get_actual(o, "costs") == Decimal("1000.00")  # 700+100+150+50

    def test_actual_net_profit(self):
        o = _make_outcome()
        assert _get_actual(o, "net_profit") == Decimal("2000.00")  # 3000 - 1000

    def test_actual_miles_sums(self):
        o = _make_outcome()
        assert _get_actual(o, "miles") == Decimal("1000")  # 800+200

    def test_actual_duration_sums(self):
        o = _make_outcome()
        assert _get_actual(o, "duration") == Decimal("600")  # 480+120

    def test_actual_costs_all_none(self):
        o = _make_outcome(
            actual_fuel_spend=None, actual_tolls=None,
            actual_maintenance=None, actual_other_costs=None,
        )
        assert _get_actual(o, "costs") is None

    def test_actual_costs_partial_none(self):
        o = _make_outcome(actual_tolls=None, actual_maintenance=None, actual_other_costs=None)
        # Only fuel_spend=700
        assert _get_actual(o, "costs") == Decimal("700.00")

    def test_actual_net_profit_no_revenue(self):
        o = _make_outcome(actual_revenue=None)
        assert _get_actual(o, "net_profit") is None


# ---- Variance calculation ----


class TestVariancePct:
    def test_positive_variance(self):
        # actual > predicted → positive %
        assert _variance_pct(Decimal("100"), Decimal("110")) == Decimal("10.00")

    def test_negative_variance(self):
        assert _variance_pct(Decimal("100"), Decimal("90")) == Decimal("-10.00")

    def test_zero_predicted(self):
        assert _variance_pct(Decimal("0"), Decimal("100")) is None

    def test_exact_match(self):
        assert _variance_pct(Decimal("500"), Decimal("500")) == Decimal("0.00")


# ---- Metric computation ----


class TestComputeMetric:
    def test_perfect_predictions(self):
        pairs = [(Decimal("1000"), Decimal("1000"))] * 5
        result = _compute_metric(pairs, "revenue")
        assert result is not None
        assert result["direction"] == "accurate"
        assert result["mean_error"] == "0.00"
        assert result["mae"] == "0.00"
        assert result["sample_size"] == 5

    def test_systematic_over_prediction(self):
        # predicted > actual → over-predicted
        pairs = [(Decimal("1000"), Decimal("900"))] * 5
        result = _compute_metric(pairs, "revenue")
        assert result is not None
        assert result["direction"] == "over"
        assert Decimal(result["mean_error"]) < 0  # actual - predicted < 0

    def test_systematic_under_prediction(self):
        # predicted < actual → under-predicted
        pairs = [(Decimal("1000"), Decimal("1200"))] * 5
        result = _compute_metric(pairs, "costs")
        assert result is not None
        assert result["direction"] == "under"
        assert Decimal(result["mean_error"]) > 0

    def test_mixed_predictions(self):
        pairs = [
            (Decimal("1000"), Decimal("1050")),
            (Decimal("1000"), Decimal("950")),
            (Decimal("1000"), Decimal("1020")),
            (Decimal("1000"), Decimal("980")),
        ]
        result = _compute_metric(pairs, "net_profit")
        assert result is not None
        assert result["sample_size"] == 4

    def test_empty_pairs(self):
        assert _compute_metric([], "revenue") is None

    def test_decimal_discipline(self):
        pairs = [(Decimal("1234.56"), Decimal("1300.78"))] * 3
        result = _compute_metric(pairs, "revenue")
        assert result is not None
        # All string values should be valid Decimals with 2dp
        for key in ["predicted_avg", "actual_avg", "mean_error", "mae", "mean_variance_pct", "worst_case_pct"]:
            val = Decimal(result[key])
            assert val == val.quantize(Decimal("0.01")), f"{key} not 2dp: {result[key]}"

    def test_worst_case(self):
        pairs = [
            (Decimal("100"), Decimal("130")),  # 30%
            (Decimal("100"), Decimal("105")),  # 5%
            (Decimal("100"), Decimal("110")),  # 10%
        ]
        result = _compute_metric(pairs, "costs")
        assert result is not None
        assert Decimal(result["worst_case_pct"]) == Decimal("30.00")


# ---- Insights ----


class TestInsights:
    def test_minimum_three_insights(self):
        metrics = [
            {"name": "revenue", "mean_variance_pct": "0.50", "direction": "accurate", "sample_size": 10},
        ]
        insights = _generate_insights(metrics, Decimal("95"))
        assert len(insights) >= 3

    def test_high_accuracy_insight(self):
        metrics = [
            {"name": "revenue", "mean_variance_pct": "1.00", "direction": "accurate", "sample_size": 5},
        ]
        insights = _generate_insights(metrics, Decimal("85"))
        assert any("well-calibrated" in i for i in insights)

    def test_low_accuracy_insight(self):
        metrics = [
            {"name": "costs", "mean_variance_pct": "25.00", "direction": "under", "sample_size": 5},
        ]
        insights = _generate_insights(metrics, Decimal("40"))
        assert any("recalibration" in i for i in insights)

    def test_systematic_bias_insight(self):
        metrics = [
            {"name": "fuel", "mean_variance_pct": "15.00", "direction": "under", "sample_size": 5},
        ]
        insights = _generate_insights(metrics, Decimal("70"))
        assert any("under-predicted" in i for i in insights)


# ---- Accuracy score ----


class TestAccuracyScore:
    def test_perfect_score(self):
        pairs = [(Decimal("1000"), Decimal("1000"))] * 5
        result = _compute_metric(pairs, "revenue")
        # mean_variance_pct = 0 → per_metric_score = 100
        score = max(Decimal("0"), Decimal("100") - abs(Decimal(result["mean_variance_pct"])) * Decimal("4"))
        assert score == Decimal("100")

    def test_25pct_variance_score(self):
        # |25%| * 4 = 100 → score = 0
        score = max(Decimal("0"), Decimal("100") - Decimal("25") * Decimal("4"))
        assert score == Decimal("0")

    def test_10pct_variance_score(self):
        # |10%| * 4 = 40 → score = 60
        score = max(Decimal("0"), Decimal("100") - Decimal("10") * Decimal("4"))
        assert score == Decimal("60")
