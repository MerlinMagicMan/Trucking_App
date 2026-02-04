"""
Tests for Calibration Feedback Loop — Stratum 5B

Covers: bias application, cap enforcement, net_profit recomputation,
quantization, confidence monotonicity, determinism.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone

from app.calibration.schemas import CalibrationProfile, PlanEstimates, CalibrationAppliedMeta
from app.calibration.profile import compute_confidence, _compute_metric_stats, _decimal_sqrt
from app.calibration.apply import (
    clamp_bias,
    apply_calibration_to_prediction,
    build_plan_estimates,
    USE_CALIBRATED_SCORING,
)


# ---- Helpers ----


def _make_profile(**overrides) -> CalibrationProfile:
    defaults = dict(
        org_id="org-1",
        window_days=30,
        sample_size=20,
        bias_pct_by_metric={
            "revenue": "5.00",
            "costs": "10.00",
            "net_profit": "-5.00",
            "miles": "3.00",
            "duration": "8.00",
        },
        volatility_pct_by_metric={
            "revenue": "8.00",
            "costs": "12.00",
            "net_profit": "15.00",
            "miles": "5.00",
            "duration": "10.00",
        },
        confidence="0.7500",
        generated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return CalibrationProfile(**defaults)


def _make_prediction() -> dict:
    return {
        "revenue": Decimal("3000.00"),
        "costs": Decimal("1500.00"),
        "net_profit": Decimal("1500.00"),
        "miles": Decimal("1000"),
        "duration": Decimal("600"),
        "profit_per_day": Decimal("214.29"),
        "planning_horizon_days": Decimal("7"),
    }


# ---- Clamp ----


class TestClampBias:
    def test_within_cap(self):
        assert clamp_bias(Decimal("0.10")) == Decimal("0.10")

    def test_positive_cap(self):
        assert clamp_bias(Decimal("0.50")) == Decimal("0.25")

    def test_negative_cap(self):
        assert clamp_bias(Decimal("-0.40")) == Decimal("-0.25")

    def test_exactly_at_cap(self):
        assert clamp_bias(Decimal("0.25")) == Decimal("0.25")

    def test_zero(self):
        assert clamp_bias(Decimal("0")) == Decimal("0")

    def test_custom_cap(self):
        assert clamp_bias(Decimal("0.50"), Decimal("0.30")) == Decimal("0.30")


# ---- Confidence ----


class TestConfidence:
    def test_increases_with_sample_size(self):
        c10 = compute_confidence(10, Decimal("10"))
        c30 = compute_confidence(30, Decimal("10"))
        c50 = compute_confidence(50, Decimal("10"))
        assert c10 < c30 < c50

    def test_decreases_with_volatility(self):
        c_low = compute_confidence(30, Decimal("5"))
        c_high = compute_confidence(30, Decimal("25"))
        assert c_low > c_high

    def test_zero_volatility(self):
        c = compute_confidence(50, Decimal("0"))
        assert c == Decimal("1.0000")

    def test_extreme_volatility(self):
        c = compute_confidence(50, Decimal("50"))
        assert c == Decimal("0.0000")

    def test_range_0_to_1(self):
        for n in [1, 5, 10, 25, 50, 100]:
            for v in [0, 5, 10, 20, 30, 50]:
                c = compute_confidence(n, Decimal(str(v)))
                assert Decimal("0") <= c <= Decimal("1"), f"n={n}, v={v}: {c}"

    def test_saturates_at_50_samples(self):
        c50 = compute_confidence(50, Decimal("10"))
        c100 = compute_confidence(100, Decimal("10"))
        assert c50 == c100  # sample factor saturates at 50


# ---- Metric stats ----


class TestMetricStats:
    def test_perfect_predictions(self):
        pairs = [(Decimal("100"), Decimal("100"))] * 5
        mean_var, vol = _compute_metric_stats(pairs)
        assert mean_var == Decimal("0.00")
        assert vol == Decimal("0.00")

    def test_systematic_bias(self):
        # All +10%
        pairs = [(Decimal("100"), Decimal("110"))] * 5
        mean_var, vol = _compute_metric_stats(pairs)
        assert mean_var == Decimal("10.00")
        assert vol == Decimal("0.00")  # no variance around mean

    def test_mixed(self):
        pairs = [
            (Decimal("100"), Decimal("110")),
            (Decimal("100"), Decimal("90")),
        ]
        mean_var, vol = _compute_metric_stats(pairs)
        assert mean_var == Decimal("0.00")  # average of +10 and -10
        assert vol > Decimal("0")  # there is variance

    def test_empty(self):
        mean_var, vol = _compute_metric_stats([])
        assert mean_var == Decimal("0")
        assert vol == Decimal("0")


# ---- Decimal sqrt ----


class TestDecimalSqrt:
    def test_perfect_square(self):
        assert abs(_decimal_sqrt(Decimal("4")) - Decimal("2")) < Decimal("0.001")

    def test_non_perfect(self):
        assert abs(_decimal_sqrt(Decimal("2")) - Decimal("1.4142")) < Decimal("0.01")

    def test_zero(self):
        assert _decimal_sqrt(Decimal("0")) == Decimal("0")


# ---- Calibration application ----


class TestApplyCalibration:
    def test_applies_bias(self):
        profile = _make_profile()
        pred = _make_prediction()
        calibrated, meta = apply_calibration_to_prediction(pred, profile)
        assert meta.applied is True
        # Revenue should be adjusted up (5% bias → actual was 5% higher → adjust up)
        assert Decimal(str(calibrated["revenue"])) > pred["revenue"]

    def test_does_not_mutate_input(self):
        profile = _make_profile()
        pred = _make_prediction()
        original_revenue = pred["revenue"]
        apply_calibration_to_prediction(pred, profile)
        assert pred["revenue"] == original_revenue

    def test_net_profit_recomputed(self):
        profile = _make_profile()
        pred = _make_prediction()
        calibrated, meta = apply_calibration_to_prediction(pred, profile)
        # net_profit should equal calibrated revenue - calibrated costs
        expected = calibrated["revenue"] - calibrated["costs"]
        assert calibrated["net_profit"] == expected.quantize(Decimal("0.01"))

    def test_cap_enforcement(self):
        profile = _make_profile(bias_pct_by_metric={
            "revenue": "50.00",  # 50% bias → should be capped to 25%
            "costs": "0.00",
            "net_profit": "0.00",
            "miles": "0.00",
            "duration": "0.00",
        })
        pred = _make_prediction()
        calibrated, meta = apply_calibration_to_prediction(pred, profile)
        assert meta.applied is True
        assert "revenue" in (meta.caps_applied or [])
        # Revenue should be 3000 * 1.25 = 3750 (not 3000 * 1.50 = 4500)
        assert calibrated["revenue"] == Decimal("3750.00")

    def test_negative_bias(self):
        profile = _make_profile(bias_pct_by_metric={
            "revenue": "-8.00",  # actual was 8% lower → adjust down
            "costs": "0.00",
            "net_profit": "0.00",
            "miles": "0.00",
            "duration": "0.00",
        })
        pred = _make_prediction()
        calibrated, meta = apply_calibration_to_prediction(pred, profile)
        assert calibrated["revenue"] < pred["revenue"]

    def test_ineligible_low_sample(self):
        profile = _make_profile(sample_size=5)
        pred = _make_prediction()
        calibrated, meta = apply_calibration_to_prediction(pred, profile)
        assert meta.applied is False
        assert any("Sample size" in e for e in meta.explanation)

    def test_ineligible_low_confidence(self):
        profile = _make_profile(confidence="0.40")
        pred = _make_prediction()
        calibrated, meta = apply_calibration_to_prediction(pred, profile)
        assert meta.applied is False
        assert any("Confidence" in e for e in meta.explanation)

    def test_volatile_metrics_skipped_individually(self):
        """All metrics volatile → applied=True but all individual metrics skipped."""
        profile = _make_profile(
            bias_pct_by_metric={
                "revenue": "10.00", "costs": "10.00",
                "net_profit": "0.00", "miles": "10.00", "duration": "10.00",
            },
            volatility_pct_by_metric={
                "revenue": "40.00", "costs": "40.00",
                "net_profit": "40.00", "miles": "40.00", "duration": "40.00",
            },
        )
        pred = _make_prediction()
        calibrated, meta = apply_calibration_to_prediction(pred, profile)
        assert meta.applied is True
        # All metrics skipped due to volatility → values unchanged
        assert calibrated["revenue"] == pred["revenue"]
        assert calibrated["costs"] == pred["costs"]

    def test_skips_volatile_metric_only(self):
        """If one metric is too volatile, skip just that metric, not all."""
        profile = _make_profile(
            bias_pct_by_metric={
                "revenue": "5.00",
                "costs": "10.00",
                "net_profit": "0.00",
                "miles": "0.00",
                "duration": "0.00",
            },
            volatility_pct_by_metric={
                "revenue": "5.00",
                "costs": "40.00",  # too volatile
                "net_profit": "5.00",
                "miles": "5.00",
                "duration": "5.00",
            },
        )
        pred = _make_prediction()
        calibrated, meta = apply_calibration_to_prediction(pred, profile)
        assert meta.applied is True
        # Revenue adjusted, costs not
        assert calibrated["revenue"] != pred["revenue"]
        assert calibrated["costs"] == pred["costs"]

    def test_determinism(self):
        profile = _make_profile()
        pred = _make_prediction()
        c1, m1 = apply_calibration_to_prediction(pred, profile)
        c2, m2 = apply_calibration_to_prediction(pred, profile)
        assert c1 == c2
        assert m1.explanation == m2.explanation

    def test_quantization_money(self):
        profile = _make_profile()
        pred = _make_prediction()
        calibrated, _ = apply_calibration_to_prediction(pred, profile)
        for key in ["revenue", "costs", "net_profit"]:
            val = calibrated[key]
            assert val == val.quantize(Decimal("0.01")), f"{key} not 2dp"

    def test_quantization_miles(self):
        profile = _make_profile()
        pred = _make_prediction()
        calibrated, _ = apply_calibration_to_prediction(pred, profile)
        val = calibrated["miles"]
        assert val == val.quantize(Decimal("0.1")), f"miles not 1dp: {val}"

    def test_quantization_duration(self):
        profile = _make_profile()
        pred = _make_prediction()
        calibrated, _ = apply_calibration_to_prediction(pred, profile)
        val = calibrated["duration"]
        assert val == val.quantize(Decimal("0.1")), f"duration not 1dp: {val}"


# ---- Build estimates ----


class TestBuildEstimates:
    def test_returns_plan_estimates(self):
        est = build_plan_estimates(
            Decimal("3000"), Decimal("1500"), Decimal("1500"),
            Decimal("214.29"), Decimal("1000"), Decimal("600"),
        )
        assert isinstance(est, PlanEstimates)
        assert est.revenue == "3000.00"
        assert est.costs == "1500.00"

    def test_all_strings(self):
        est = build_plan_estimates(
            Decimal("3000"), Decimal("1500"), Decimal("1500"),
            Decimal("214.29"), Decimal("1000"), Decimal("600"),
        )
        for field in ["revenue", "costs", "net_profit", "profit_per_day", "miles", "duration_min"]:
            val = getattr(est, field)
            assert isinstance(val, str), f"{field} is not str"
            # Should parse as Decimal
            Decimal(val)


# ---- Config flag ----


class TestConfigFlag:
    def test_use_calibrated_scoring_exists(self):
        assert isinstance(USE_CALIBRATED_SCORING, bool)
