"""
Tests for Trust Engine — Stratum 5C

Covers: determinism, penalty thresholds, adjustment calculation,
confidence labeling, warning generation.
"""
import pytest
from decimal import Decimal

from app.trust.engine import (
    dec,
    quant2,
    compute_adjustment_pct,
    compute_complexity_penalty,
    compute_offline_penalty,
    compute_volatility_penalty,
    compute_adjustment_penalty,
    compute_confidence_score,
    label_confidence,
    build_warnings,
    build_explanations,
)


# ---- Decimal helpers ----


class TestDecimalHelpers:
    def test_dec_none(self):
        assert dec(None) == Decimal("0")

    def test_dec_string(self):
        assert dec("123.45") == Decimal("123.45")

    def test_dec_int(self):
        assert dec(100) == Decimal("100")

    def test_dec_float(self):
        # Avoids float precision issues
        assert dec(0.1) == Decimal("0.1")

    def test_dec_decimal(self):
        assert dec(Decimal("50")) == Decimal("50")

    def test_quant2(self):
        assert quant2(Decimal("123.456")) == Decimal("123.46")
        assert quant2(Decimal("99.994")) == Decimal("99.99")


# ---- Adjustment calculation ----


class TestAdjustmentPct:
    def test_no_change(self):
        raw = {"revenue": "1000", "costs": "500", "net_profit": "500", "miles": "400", "duration_min": "600"}
        cal = {"revenue": "1000", "costs": "500", "net_profit": "500", "miles": "400", "duration_min": "600"}
        result = compute_adjustment_pct(raw, cal)
        assert result["revenue"] == Decimal("0.00")
        assert result["costs"] == Decimal("0.00")

    def test_10pct_increase(self):
        raw = {"revenue": "1000", "costs": "500", "net_profit": "500", "miles": "400", "duration_min": "600"}
        cal = {"revenue": "1100", "costs": "500", "net_profit": "600", "miles": "400", "duration_min": "600"}
        result = compute_adjustment_pct(raw, cal)
        assert result["revenue"] == Decimal("10.00")

    def test_20pct_decrease(self):
        raw = {"revenue": "1000", "costs": "500", "net_profit": "500", "miles": "400", "duration_min": "600"}
        cal = {"revenue": "800", "costs": "500", "net_profit": "300", "miles": "400", "duration_min": "600"}
        result = compute_adjustment_pct(raw, cal)
        assert result["revenue"] == Decimal("20.00")

    def test_zero_raw_uses_1_as_divisor(self):
        raw = {"revenue": "0", "costs": "0", "net_profit": "0", "miles": "0", "duration_min": "0"}
        cal = {"revenue": "100", "costs": "50", "net_profit": "50", "miles": "10", "duration_min": "60"}
        result = compute_adjustment_pct(raw, cal)
        # Uses max(abs(0), 1) = 1 as divisor
        assert result["revenue"] == Decimal("10000.00")


# ---- Complexity penalty ----


class TestComplexityPenalty:
    def test_short_simple(self):
        # 10h, 2 loads
        penalty = compute_complexity_penalty(Decimal("600"), 2)
        assert penalty == Decimal("0")

    def test_18h_2loads(self):
        penalty = compute_complexity_penalty(Decimal("1080"), 2)
        assert penalty == Decimal("0.08")

    def test_30h_2loads(self):
        penalty = compute_complexity_penalty(Decimal("1800"), 2)
        assert penalty == Decimal("0.14")

    def test_10h_3loads(self):
        penalty = compute_complexity_penalty(Decimal("600"), 3)
        assert penalty == Decimal("0.06")

    def test_10h_5loads(self):
        penalty = compute_complexity_penalty(Decimal("600"), 5)
        assert penalty == Decimal("0.12")

    def test_30h_5loads_capped(self):
        # 0.14 + 0.12 = 0.26 → capped to 0.25
        penalty = compute_complexity_penalty(Decimal("1800"), 5)
        assert penalty == Decimal("0.25")


# ---- Offline penalty ----


class TestOfflinePenalty:
    def test_offline_true(self):
        assert compute_offline_penalty(True, 0) == Decimal("0.25")
        assert compute_offline_penalty(True, 3) == Decimal("0.25")

    def test_no_missing(self):
        assert compute_offline_penalty(False, 0) == Decimal("0")

    def test_1_missing(self):
        assert compute_offline_penalty(False, 1) == Decimal("0.06")

    def test_3_missing_capped(self):
        # 3 * 0.06 = 0.18
        assert compute_offline_penalty(False, 3) == Decimal("0.18")

    def test_5_missing_capped(self):
        # 5 * 0.06 = 0.30 → capped to 0.18
        assert compute_offline_penalty(False, 5) == Decimal("0.18")


# ---- Volatility penalty ----


class TestVolatilityPenalty:
    def test_empty(self):
        assert compute_volatility_penalty({}) == Decimal("0")

    def test_low_volatility(self):
        assert compute_volatility_penalty({"costs": "10", "revenue": "8"}) == Decimal("0")

    def test_20pct_threshold(self):
        assert compute_volatility_penalty({"costs": "20"}) == Decimal("0.10")

    def test_35pct_threshold(self):
        assert compute_volatility_penalty({"costs": "35"}) == Decimal("0.22")

    def test_two_metrics_over_20(self):
        # costs 25%, revenue 22% → base 0.10 + 0.05 = 0.15
        assert compute_volatility_penalty({"costs": "25", "revenue": "22"}) == Decimal("0.15")

    def test_high_volatility_with_multiple_metrics(self):
        # Very high volatility: 50% costs → 0.22, 3 metrics > 20% → +0.05 = 0.27
        assert compute_volatility_penalty({"costs": "50", "revenue": "45", "miles": "40"}) == Decimal("0.27")


# ---- Adjustment penalty ----


class TestAdjustmentPenalty:
    def test_low_adjustment(self):
        assert compute_adjustment_penalty({"revenue": Decimal("5"), "costs": Decimal("8")}) == Decimal("0")

    def test_12pct_threshold(self):
        assert compute_adjustment_penalty({"revenue": Decimal("12"), "costs": Decimal("5")}) == Decimal("0.10")

    def test_20pct_threshold(self):
        assert compute_adjustment_penalty({"revenue": Decimal("20"), "costs": Decimal("5")}) == Decimal("0.18")

    def test_empty(self):
        assert compute_adjustment_penalty({}) == Decimal("0")


# ---- Confidence score ----


class TestConfidenceScore:
    def test_none_profile_returns_0(self):
        assert compute_confidence_score(None, Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")) == 0

    def test_perfect_score(self):
        # 1.0 confidence, no penalties → 100
        score = compute_confidence_score(
            Decimal("1.0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")
        )
        assert score == 100

    def test_half_confidence(self):
        # 0.5 confidence, no penalties → 50
        score = compute_confidence_score(
            Decimal("0.5"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")
        )
        assert score == 50

    def test_penalties_reduce_score(self):
        # 1.0 confidence, 0.20 total penalties → 80
        score = compute_confidence_score(
            Decimal("1.0"), Decimal("0.10"), Decimal("0.05"), Decimal("0.03"), Decimal("0.02")
        )
        assert score == 80

    def test_score_clamped_at_0(self):
        # 1.0 confidence, 1.5 penalties → 0 (not negative)
        score = compute_confidence_score(
            Decimal("1.0"), Decimal("0.5"), Decimal("0.5"), Decimal("0.25"), Decimal("0.25")
        )
        assert score == 0


# ---- Confidence label ----


class TestConfidenceLabel:
    def test_low_sample_unknown(self):
        assert label_confidence(80, False, 5) == "unknown"

    def test_offline_low_score_unknown(self):
        assert label_confidence(50, True, 20) == "unknown"

    def test_high(self):
        assert label_confidence(80, False, 20) == "high"
        assert label_confidence(95, False, 20) == "high"

    def test_medium(self):
        assert label_confidence(55, False, 20) == "medium"
        assert label_confidence(79, False, 20) == "medium"

    def test_low(self):
        assert label_confidence(54, False, 20) == "low"
        assert label_confidence(30, False, 20) == "low"


# ---- Warnings ----


class TestBuildWarnings:
    def test_low_sample_size_high(self):
        warnings = build_warnings(
            sample_size=5,
            profile_confidence=Decimal("0.80"),
            volatility_pct={},
            adjustment_pct={},
            offline=False,
            missing_intel_kinds=[],
            plan_duration_min=Decimal("600"),
            num_loads=2,
        )
        kinds = [w.kind for w in warnings]
        assert "low_sample_size" in kinds
        assert any(w.severity == "high" and w.kind == "low_sample_size" for w in warnings)

    def test_low_sample_size_medium(self):
        warnings = build_warnings(
            sample_size=15,
            profile_confidence=Decimal("0.80"),
            volatility_pct={},
            adjustment_pct={},
            offline=False,
            missing_intel_kinds=[],
            plan_duration_min=Decimal("600"),
            num_loads=2,
        )
        kinds = [w.kind for w in warnings]
        assert "low_sample_size" in kinds
        assert any(w.severity == "medium" and w.kind == "low_sample_size" for w in warnings)

    def test_no_sample_warning_at_25(self):
        warnings = build_warnings(
            sample_size=25,
            profile_confidence=Decimal("0.80"),
            volatility_pct={},
            adjustment_pct={},
            offline=False,
            missing_intel_kinds=[],
            plan_duration_min=Decimal("600"),
            num_loads=2,
        )
        kinds = [w.kind for w in warnings]
        assert "low_sample_size" not in kinds

    def test_offline_warning(self):
        warnings = build_warnings(
            sample_size=25,
            profile_confidence=Decimal("0.80"),
            volatility_pct={},
            adjustment_pct={},
            offline=True,
            missing_intel_kinds=[],
            plan_duration_min=Decimal("600"),
            num_loads=2,
        )
        kinds = [w.kind for w in warnings]
        assert "offline_intel" in kinds

    def test_large_adjustment_warning(self):
        warnings = build_warnings(
            sample_size=25,
            profile_confidence=Decimal("0.80"),
            volatility_pct={},
            adjustment_pct={"revenue": Decimal("25"), "costs": Decimal("5")},
            offline=False,
            missing_intel_kinds=[],
            plan_duration_min=Decimal("600"),
            num_loads=2,
        )
        kinds = [w.kind for w in warnings]
        assert "large_calibration_adjustment" in kinds

    def test_load_unavailable_from_copilot(self):
        warnings = build_warnings(
            sample_size=25,
            profile_confidence=Decimal("0.80"),
            volatility_pct={},
            adjustment_pct={},
            offline=False,
            missing_intel_kinds=[],
            plan_duration_min=Decimal("600"),
            num_loads=2,
            copilot_signals=[{"kind": "load_unavailable", "severity": "high", "details": {}}],
        )
        kinds = [w.kind for w in warnings]
        assert "load_unavailable" in kinds


# ---- Explanations ----


class TestBuildExplanations:
    def test_minimum_3(self):
        explanations = build_explanations(
            sample_size=25,
            window_days=30,
            profile_confidence=Decimal("0.80"),
            volatility_penalty=Decimal("0"),
            adjustment_penalty=Decimal("0"),
            complexity_penalty=Decimal("0"),
            offline_penalty=Decimal("0"),
            confidence_score=80,
            confidence_label="high",
        )
        assert len(explanations) >= 3

    def test_mentions_sample_size(self):
        explanations = build_explanations(
            sample_size=15,
            window_days=30,
            profile_confidence=Decimal("0.60"),
            volatility_penalty=Decimal("0.10"),
            adjustment_penalty=Decimal("0"),
            complexity_penalty=Decimal("0"),
            offline_penalty=Decimal("0"),
            confidence_score=50,
            confidence_label="low",
        )
        assert any("15" in e for e in explanations)
        assert any("30 days" in e for e in explanations)


# ---- Determinism ----


class TestDeterminism:
    def test_same_inputs_same_score(self):
        args = (
            Decimal("0.75"),
            Decimal("0.10"),
            Decimal("0.05"),
            Decimal("0.08"),
            Decimal("0.06"),
        )
        score1 = compute_confidence_score(*args)
        score2 = compute_confidence_score(*args)
        assert score1 == score2

    def test_same_inputs_same_warnings(self):
        kwargs = dict(
            sample_size=18,
            profile_confidence=Decimal("0.55"),
            volatility_pct={"costs": "22"},
            adjustment_pct={"revenue": Decimal("15")},
            offline=False,
            missing_intel_kinds=["lane"],
            plan_duration_min=Decimal("1200"),
            num_loads=3,
        )
        w1 = build_warnings(**kwargs)
        w2 = build_warnings(**kwargs)
        assert len(w1) == len(w2)
        assert [w.kind for w in w1] == [w.kind for w in w2]
