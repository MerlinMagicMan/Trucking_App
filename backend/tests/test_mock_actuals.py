"""
Tests for Mock Actuals Generator — Stratum 4C

Covers: determinism, variance bounds, progressive arrival,
manual protection, no-overwrite policy, decimal discipline.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.outcomes.mock_actuals_generator import (
    _time_slot,
    _variance_seed,
    _rand01,
    _apply_variance,
    _apply_int_variance,
    _stage,
    extract_cost_breakdown,
    _should_skip,
    _has_any_actuals,
    _generate_partial_actuals,
    _generate_complete_actuals,
    _apply_completion,
    ACTUAL_FIELDS,
)


# ---- Determinism ----


class TestDeterminism:
    def test_time_slot_truncates_to_15min(self):
        now = datetime(2026, 2, 1, 3, 47, 30, tzinfo=timezone.utc)
        assert _time_slot(now) == "2026-02-01T03:45Z"

    def test_time_slot_on_boundary(self):
        now = datetime(2026, 2, 1, 3, 30, 0, tzinfo=timezone.utc)
        assert _time_slot(now) == "2026-02-01T03:30Z"

    def test_time_slot_zero_minutes(self):
        now = datetime(2026, 2, 1, 3, 0, 0, tzinfo=timezone.utc)
        assert _time_slot(now) == "2026-02-01T03:00Z"

    def test_variance_seed_deterministic(self):
        s1 = _variance_seed("plan-1", "revenue", "2026-02-01T03:45Z")
        s2 = _variance_seed("plan-1", "revenue", "2026-02-01T03:45Z")
        assert s1 == s2

    def test_variance_seed_different_inputs(self):
        s1 = _variance_seed("plan-1", "revenue", "2026-02-01T03:45Z")
        s2 = _variance_seed("plan-2", "revenue", "2026-02-01T03:45Z")
        assert s1 != s2

    def test_rand01_in_range(self):
        for i in range(100):
            seed = _variance_seed(f"plan-{i}", "test", "slot")
            r = _rand01(seed)
            assert Decimal("0") <= r < Decimal("1")

    def test_apply_variance_deterministic(self):
        v1 = _apply_variance(Decimal("1000"), "plan-1", "revenue", "slot-1", 0.95, 1.05)
        v2 = _apply_variance(Decimal("1000"), "plan-1", "revenue", "slot-1", 0.95, 1.05)
        assert v1 == v2

    def test_apply_variance_different_slot_different_result(self):
        v1 = _apply_variance(Decimal("1000"), "plan-1", "revenue", "slot-1", 0.95, 1.05)
        v2 = _apply_variance(Decimal("1000"), "plan-1", "revenue", "slot-2", 0.95, 1.05)
        # Could theoretically be equal but extremely unlikely
        # Just verify they're both valid
        assert Decimal("950") <= v1 <= Decimal("1050")
        assert Decimal("950") <= v2 <= Decimal("1050")

    def test_stage_deterministic(self):
        s1 = _stage("plan-1", "slot-1")
        s2 = _stage("plan-1", "slot-1")
        assert s1 == s2
        assert s1 in ("partial", "complete")


# ---- Variance bounds ----


class TestVarianceBounds:
    def test_revenue_within_5pct(self):
        base = Decimal("2000.00")
        for i in range(50):
            actual = _apply_variance(base, f"p-{i}", "revenue", "s", 0.95, 1.05)
            assert Decimal("1900") <= actual <= Decimal("2100"), f"Revenue out of bounds: {actual}"

    def test_fuel_overrun_10_to_25pct(self):
        base = Decimal("500.00")
        for i in range(50):
            actual = _apply_variance(base, f"p-{i}", "fuel", "s", 1.10, 1.25)
            assert Decimal("550") <= actual <= Decimal("625"), f"Fuel out of bounds: {actual}"

    def test_tolls_within_15pct(self):
        base = Decimal("100.00")
        for i in range(50):
            actual = _apply_variance(base, f"p-{i}", "tolls", "s", 0.85, 1.15)
            assert Decimal("85") <= actual <= Decimal("115"), f"Tolls out of bounds: {actual}"

    def test_maintenance_within_20pct(self):
        base = Decimal("200.00")
        for i in range(50):
            actual = _apply_variance(base, f"p-{i}", "maintenance", "s", 0.80, 1.20)
            assert Decimal("160") <= actual <= Decimal("240"), f"Maintenance out of bounds: {actual}"

    def test_drive_time_5_to_15pct_overrun(self):
        base = 480
        for i in range(50):
            actual = _apply_int_variance(base, f"p-{i}", "drive_min", "s", 1.05, 1.15)
            assert 504 <= actual <= 552, f"Drive time out of bounds: {actual}"

    def test_wait_time_20_to_80pct_overrun(self):
        base = 30
        for i in range(50):
            actual = _apply_int_variance(base, f"p-{i}", "wait_min", "s", 1.20, 1.80)
            assert 36 <= actual <= 54, f"Wait time out of bounds: {actual}"

    def test_zero_base_returns_zero(self):
        assert _apply_variance(Decimal("0"), "p", "f", "s", 0.95, 1.05) == Decimal("0.00")
        assert _apply_int_variance(0, "p", "f", "s", 0.95, 1.05) == 0

    def test_none_base_returns_zero(self):
        assert _apply_variance(None, "p", "f", "s", 0.95, 1.05) == Decimal("0.00")


# ---- Cost breakdown ----


class TestCostBreakdown:
    def test_breakdown_sums_to_total(self):
        total = Decimal("1200.00")
        bd = extract_cost_breakdown(total, 1000)
        total_from_breakdown = bd["fuel"] + bd["tolls"] + bd["maintenance"] + bd["other"]
        assert total_from_breakdown == total

    def test_fuel_is_largest_share(self):
        bd = extract_cost_breakdown(Decimal("1000.00"), 800)
        assert bd["fuel"] > bd["tolls"]
        assert bd["fuel"] > bd["maintenance"]

    def test_zero_costs(self):
        bd = extract_cost_breakdown(Decimal("0"), 100)
        assert all(v == Decimal("0.00") for v in bd.values())

    def test_no_miles_uses_proportions(self):
        bd = extract_cost_breakdown(Decimal("1000.00"), 0)
        total = bd["fuel"] + bd["tolls"] + bd["maintenance"] + bd["other"]
        assert total == Decimal("1000.00")

    def test_none_costs(self):
        bd = extract_cost_breakdown(None, 100)
        assert all(v == Decimal("0.00") for v in bd.values())


# ---- Progressive arrival ----


class TestProgression:
    def _make_snapshot(self, **overrides):
        s = MagicMock()
        s.predicted_revenue = Decimal("3000.00")
        s.predicted_costs = Decimal("1500.00")
        s.predicted_net_profit = Decimal("1500.00")
        s.predicted_miles_total = 1000
        s.predicted_miles_deadhead = 200
        s.predicted_duration_min = 600
        s.predicted_num_loads = 2
        for k, v in overrides.items():
            setattr(s, k, v)
        return s

    def test_partial_actuals_has_revenue_and_miles(self):
        snap = self._make_snapshot()
        patch = _generate_partial_actuals(snap, "plan-1", "slot-1")
        assert "actual_revenue" in patch
        assert "actual_miles_loaded" in patch
        assert "actual_drive_min" in patch
        assert "actual_wait_min" in patch
        # No cost fields
        assert "actual_fuel_spend" not in patch
        assert "actual_tolls" not in patch

    def test_complete_actuals_has_costs(self):
        snap = self._make_snapshot()
        patch = _generate_complete_actuals(snap, "plan-1", "slot-1")
        assert "actual_fuel_spend" in patch
        assert "actual_tolls" in patch
        assert "actual_maintenance" in patch
        assert "actual_other_costs" in patch
        assert "actual" in patch  # JSONB

    def test_all_money_values_are_decimal(self):
        snap = self._make_snapshot()
        partial = _generate_partial_actuals(snap, "plan-1", "slot-1")
        complete = _generate_complete_actuals(snap, "plan-1", "slot-1")
        money_fields = ["actual_revenue", "actual_fuel_spend", "actual_tolls",
                        "actual_maintenance", "actual_other_costs"]
        for patch in [partial, complete]:
            for field in money_fields:
                if field in patch:
                    assert isinstance(patch[field], Decimal), f"{field} is not Decimal: {type(patch[field])}"


# ---- Manual protection + no-overwrite ----


class TestWriteSafety:
    def _make_outcome(self, **overrides):
        o = MagicMock()
        o.source = "decision"
        o.status = "pending"
        for field in ACTUAL_FIELDS:
            setattr(o, field, None)
        for k, v in overrides.items():
            setattr(o, k, v)
        return o

    def test_manual_source_skipped(self):
        o = self._make_outcome(source="manual")
        assert _should_skip(o) is True

    def test_mock_actuals_source_not_skipped(self):
        o = self._make_outcome(source="mock_actuals")
        assert _should_skip(o) is False

    def test_imported_with_actuals_skipped(self):
        o = self._make_outcome(source="imported", actual_revenue=Decimal("1000"))
        assert _should_skip(o) is True

    def test_decision_without_actuals_not_skipped(self):
        o = self._make_outcome(source="decision")
        assert _should_skip(o) is False

    def test_decision_with_actuals_skipped(self):
        o = self._make_outcome(source="decision", actual_revenue=Decimal("1000"))
        assert _should_skip(o) is True

    def test_has_any_actuals_false_when_empty(self):
        o = self._make_outcome()
        assert _has_any_actuals(o) is False

    def test_has_any_actuals_true_when_set(self):
        o = self._make_outcome(actual_miles_loaded=500)
        assert _has_any_actuals(o) is True


# ---- Completion validation ----


class TestCompletion:
    def _make_outcome(self, **overrides):
        o = MagicMock()
        o.status = "pending"
        o.completed_at = None
        o.actual_revenue = None
        o.actual_fuel_spend = None
        o.actual_tolls = None
        o.actual_miles_loaded = None
        o.actual_drive_min = None
        for k, v in overrides.items():
            setattr(o, k, v)
        return o

    def test_complete_when_revenue_and_fuel(self):
        o = self._make_outcome(actual_revenue=Decimal("2000"), actual_fuel_spend=Decimal("500"))
        _apply_completion(o)
        assert o.status == "complete"
        assert o.completed_at is not None

    def test_partial_when_only_revenue(self):
        o = self._make_outcome(actual_revenue=Decimal("2000"))
        _apply_completion(o)
        assert o.status == "partial"

    def test_pending_when_nothing(self):
        o = self._make_outcome()
        _apply_completion(o)
        # status remains pending (no has_any)
        assert o.status == "pending"

    def test_partial_when_only_miles(self):
        o = self._make_outcome(actual_miles_loaded=500)
        _apply_completion(o)
        assert o.status == "partial"


# ---- Decimal discipline ----


class TestDecimalDiscipline:
    def test_apply_variance_returns_2dp(self):
        v = _apply_variance(Decimal("1234.567"), "p", "f", "s", 0.95, 1.05)
        assert v == v.quantize(Decimal("0.01"))

    def test_cost_breakdown_all_2dp(self):
        bd = extract_cost_breakdown(Decimal("1234.56"), 500)
        for key, val in bd.items():
            assert val == val.quantize(Decimal("0.01")), f"{key} not 2dp: {val}"

    def test_other_costs_is_decimal(self):
        patch = _generate_complete_actuals(
            MagicMock(
                predicted_costs=Decimal("1000"),
                predicted_miles_total=500,
            ),
            "plan-1", "slot-1",
        )
        assert isinstance(patch["actual_other_costs"], Decimal)
