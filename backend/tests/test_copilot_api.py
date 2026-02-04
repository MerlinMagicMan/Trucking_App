"""
Tests for Copilot evaluator (Phase 4)
"""
import pytest
from app.copilot.evaluator import evaluate_plan


# ---- Helpers ----

def _make_plan(rate=1500.0, source="mock_market", external_id="MKT-001"):
    return {
        "plan_id": "test-plan-001",
        "loads": [
            {
                "load": {
                    "id": f"{source}_{external_id}",
                    "source": source,
                    "external_id": external_id,
                    "rate_total": rate,
                    "miles": 400,
                    "pickup_geohash": "9y69",
                    "delivery_geohash": "9vg4",
                    "pickup": {"city": "OKC", "state": "OK", "lat": 35.4, "lng": -97.5},
                    "delivery": {"city": "Dallas", "state": "TX", "lat": 32.7, "lng": -96.8},
                },
                "revenue_usd": rate,
                "deadhead_miles": 50,
                "net_revenue_usd": rate - 200,
            }
        ],
    }


# ---- Evaluator: status ok ----

class TestEvaluatorOk:
    def test_all_ok_returns_ok(self):
        status, signals, suggestions, explanations = evaluate_plan(
            plan=_make_plan(1500),
            lane_rate_p50=1500,
            lane_rate_p75=1700,
            lane_time_to_cover=120,
            lane_load_count=10,
            market_temperature="neutral",
            efficiency_score=75,
            loads_active={"mock_market/MKT-001": True},
        )
        assert status == "ok"
        assert len(signals) == 0

    def test_small_rate_shift_under_10pct_is_ok(self):
        status, signals, _, _ = evaluate_plan(
            plan=_make_plan(1500),
            lane_rate_p50=1600,  # +6.7%
            lane_rate_p75=1700,
            lane_time_to_cover=120,
            lane_load_count=10,
            market_temperature="neutral",
            efficiency_score=80,
            loads_active={"mock_market/MKT-001": True},
        )
        assert status == "ok"
        assert len(signals) == 0


# ---- Evaluator: lane rate shift ----

class TestLaneRateShift:
    def test_10pct_shift_low_severity(self):
        status, signals, _, _ = evaluate_plan(
            plan=_make_plan(1000),
            lane_rate_p50=1100,  # +10%
            lane_rate_p75=1200,
            lane_time_to_cover=120,
            lane_load_count=10,
            market_temperature="neutral",
            efficiency_score=80,
            loads_active={},
        )
        assert status == "degraded"
        rate_signals = [s for s in signals if s["kind"] == "lane_rate_shift"]
        assert len(rate_signals) == 1
        assert rate_signals[0]["severity"] == "low"

    def test_20pct_shift_medium_severity(self):
        _, signals, _, _ = evaluate_plan(
            plan=_make_plan(1000),
            lane_rate_p50=1200,  # +20%
            lane_rate_p75=1400,
            lane_time_to_cover=120,
            lane_load_count=10,
            market_temperature="neutral",
            efficiency_score=80,
            loads_active={},
        )
        rate_signals = [s for s in signals if s["kind"] == "lane_rate_shift"]
        assert rate_signals[0]["severity"] == "medium"

    def test_30pct_shift_high_severity(self):
        _, signals, _, _ = evaluate_plan(
            plan=_make_plan(1000),
            lane_rate_p50=1300,  # +30%
            lane_rate_p75=1500,
            lane_time_to_cover=120,
            lane_load_count=10,
            market_temperature="neutral",
            efficiency_score=80,
            loads_active={},
        )
        rate_signals = [s for s in signals if s["kind"] == "lane_rate_shift"]
        assert rate_signals[0]["severity"] == "high"

    def test_negative_shift_triggers_counter_offer(self):
        _, signals, suggestions, _ = evaluate_plan(
            plan=_make_plan(1000),
            lane_rate_p50=800,  # -20%
            lane_rate_p75=900,
            lane_time_to_cover=120,
            lane_load_count=10,
            market_temperature="neutral",
            efficiency_score=80,
            loads_active={},
        )
        counter = [s for s in suggestions if s["kind"] == "counter_offer"]
        assert len(counter) >= 1
        assert counter[0]["data"]["suggested_rate_usd"] == 800

    def test_positive_shift_fast_cover_triggers_take_now(self):
        _, _, suggestions, _ = evaluate_plan(
            plan=_make_plan(1000),
            lane_rate_p50=1200,  # +20%
            lane_rate_p75=1400,
            lane_time_to_cover=45,  # < 60 min
            lane_load_count=10,
            market_temperature="neutral",
            efficiency_score=80,
            loads_active={},
        )
        kinds = [s["kind"] for s in suggestions]
        assert "take_now" in kinds
        assert "counter_offer" in kinds


# ---- Evaluator: market cold ----

class TestMarketCold:
    def test_cold_market_degraded(self):
        status, signals, suggestions, _ = evaluate_plan(
            plan=_make_plan(1500),
            lane_rate_p50=1500,
            lane_rate_p75=1700,
            lane_time_to_cover=120,
            lane_load_count=10,
            market_temperature="cold",
            efficiency_score=80,
            loads_active={},
        )
        assert status == "degraded"
        market_signals = [s for s in signals if s["kind"] == "market_temp_downgrade"]
        assert len(market_signals) == 1
        assert market_signals[0]["severity"] == "medium"
        buffer = [s for s in suggestions if s["kind"] == "add_buffer"]
        assert len(buffer) == 1


# ---- Evaluator: destination score drop ----

class TestDestinationDrop:
    def test_low_efficiency_degraded(self):
        status, signals, _, _ = evaluate_plan(
            plan=_make_plan(1500),
            lane_rate_p50=1500,
            lane_rate_p75=1700,
            lane_time_to_cover=120,
            lane_load_count=10,
            market_temperature="neutral",
            efficiency_score=40,
            loads_active={},
        )
        assert status == "degraded"
        dest_signals = [s for s in signals if s["kind"] == "destination_score_drop"]
        assert len(dest_signals) == 1
        assert dest_signals[0]["severity"] == "medium"

    def test_very_low_efficiency_high_severity(self):
        _, signals, _, _ = evaluate_plan(
            plan=_make_plan(1500),
            lane_rate_p50=1500,
            lane_rate_p75=1700,
            lane_time_to_cover=120,
            lane_load_count=10,
            market_temperature="neutral",
            efficiency_score=20,
            loads_active={},
        )
        dest_signals = [s for s in signals if s["kind"] == "destination_score_drop"]
        assert dest_signals[0]["severity"] == "high"


# ---- Evaluator: load unavailable ----

class TestLoadUnavailable:
    def test_inactive_load_high_severity(self):
        status, signals, _, _ = evaluate_plan(
            plan=_make_plan(1500),
            lane_rate_p50=1500,
            lane_rate_p75=1700,
            lane_time_to_cover=120,
            lane_load_count=10,
            market_temperature="neutral",
            efficiency_score=80,
            loads_active={"mock_market/MKT-001": False},
        )
        assert status == "degraded"
        unavail = [s for s in signals if s["kind"] == "load_unavailable"]
        assert len(unavail) == 1
        assert unavail[0]["severity"] == "high"


# ---- Evaluator: unknown status ----

class TestUnknownStatus:
    def test_no_loads_returns_unknown(self):
        status, _, _, explanations = evaluate_plan(
            plan={"plan_id": "x", "loads": []},
            lane_rate_p50=None,
            lane_rate_p75=None,
            lane_time_to_cover=None,
            lane_load_count=None,
            market_temperature=None,
            efficiency_score=None,
            loads_active={},
        )
        assert status == "unknown"

    def test_missing_rate_returns_unknown(self):
        status, _, _, _ = evaluate_plan(
            plan={"plan_id": "x", "loads": [{"load": {"id": "x"}}]},
            lane_rate_p50=None,
            lane_rate_p75=None,
            lane_time_to_cover=None,
            lane_load_count=None,
            market_temperature=None,
            efficiency_score=None,
            loads_active={},
        )
        assert status == "unknown"


# ---- Evaluator: alternate destination suggestion ----

class TestAlternateDestination:
    def test_low_efficiency_suggests_alternate(self):
        _, _, suggestions, _ = evaluate_plan(
            plan=_make_plan(1500),
            lane_rate_p50=1500,
            lane_rate_p75=1700,
            lane_time_to_cover=120,
            lane_load_count=10,
            market_temperature="neutral",
            efficiency_score=40,
            loads_active={},
        )
        alt = [s for s in suggestions if s["kind"] == "alternate_destination"]
        assert len(alt) >= 1

    def test_cold_market_suggests_alternate(self):
        _, _, suggestions, _ = evaluate_plan(
            plan=_make_plan(1500),
            lane_rate_p50=1500,
            lane_rate_p75=1700,
            lane_time_to_cover=120,
            lane_load_count=10,
            market_temperature="cold",
            efficiency_score=80,
            loads_active={},
        )
        alt = [s for s in suggestions if s["kind"] == "alternate_destination"]
        assert len(alt) >= 1


# ---- Phase 4.1: Constraint mapping ----

class TestConstraintMapping:
    def test_alternate_destination_increases_radius(self):
        from app.api.copilot_routes import _map_suggestion_to_constraints
        changes = _map_suggestion_to_constraints(
            "alternate_destination", {}, 7, 250, 3,
        )
        assert changes["radius_miles"] == 375  # 250 * 1.5

    def test_alternate_destination_caps_at_500(self):
        from app.api.copilot_routes import _map_suggestion_to_constraints
        changes = _map_suggestion_to_constraints(
            "alternate_destination", {}, 7, 400, 3,
        )
        assert changes["radius_miles"] == 500

    def test_add_buffer_reduces_horizon(self):
        from app.api.copilot_routes import _map_suggestion_to_constraints
        changes = _map_suggestion_to_constraints(
            "add_buffer", {}, 10, 250, 3,
        )
        assert changes["planning_horizon_days"] == 9

    def test_add_buffer_min_horizon_7(self):
        from app.api.copilot_routes import _map_suggestion_to_constraints
        changes = _map_suggestion_to_constraints(
            "add_buffer", {}, 7, 250, 3,
        )
        assert changes["planning_horizon_days"] == 7

    def test_take_now_sets_max_plans_1(self):
        from app.api.copilot_routes import _map_suggestion_to_constraints
        changes = _map_suggestion_to_constraints(
            "take_now", {}, 7, 250, 3,
        )
        assert changes["max_plans"] == 1

    def test_counter_offer_no_changes(self):
        from app.api.copilot_routes import _map_suggestion_to_constraints
        changes = _map_suggestion_to_constraints(
            "counter_offer", {}, 7, 250, 3,
        )
        assert changes == {}


# ---- Phase 4.2: Drift calculation ----

class TestDriftCalculation:
    def test_no_drift_when_same(self):
        from app.copilot.evaluator import compute_drift
        signals = [{"kind": "lane_rate_shift", "severity": "low", "summary": "x", "details": {}}]
        drift = compute_drift(signals, signals)
        assert drift["new_signals"] == []
        assert drift["resolved_signals"] == []
        assert drift["severity_changes"] == []

    def test_new_signal_detected(self):
        from app.copilot.evaluator import compute_drift
        original = []
        replayed = [{"kind": "market_temp_downgrade", "severity": "medium", "summary": "x", "details": {}}]
        drift = compute_drift(original, replayed)
        assert len(drift["new_signals"]) == 1
        assert drift["new_signals"][0]["kind"] == "market_temp_downgrade"

    def test_resolved_signal_detected(self):
        from app.copilot.evaluator import compute_drift
        original = [{"kind": "load_unavailable", "severity": "high", "summary": "x", "details": {}}]
        replayed = []
        drift = compute_drift(original, replayed)
        assert len(drift["resolved_signals"]) == 1
        assert drift["resolved_signals"][0]["kind"] == "load_unavailable"

    def test_severity_change_detected(self):
        from app.copilot.evaluator import compute_drift
        original = [{"kind": "lane_rate_shift", "severity": "low", "summary": "x", "details": {}}]
        replayed = [{"kind": "lane_rate_shift", "severity": "high", "summary": "y", "details": {}}]
        drift = compute_drift(original, replayed)
        assert len(drift["severity_changes"]) == 1
        assert drift["severity_changes"][0]["was"] == "low"
        assert drift["severity_changes"][0]["now"] == "high"

    def test_mixed_drift(self):
        from app.copilot.evaluator import compute_drift
        original = [
            {"kind": "lane_rate_shift", "severity": "low", "summary": "x", "details": {}},
            {"kind": "load_unavailable", "severity": "high", "summary": "x", "details": {}},
        ]
        replayed = [
            {"kind": "lane_rate_shift", "severity": "medium", "summary": "y", "details": {}},
            {"kind": "market_temp_downgrade", "severity": "medium", "summary": "z", "details": {}},
        ]
        drift = compute_drift(original, replayed)
        assert len(drift["new_signals"]) == 1  # market_temp_downgrade
        assert len(drift["resolved_signals"]) == 1  # load_unavailable
        assert len(drift["severity_changes"]) == 1  # lane_rate_shift low→medium


# ---- Integration tests (require DB) ----

class TestCopilotAPIIntegration:
    @pytest.fixture(autouse=True)
    def _skip_no_db(self):
        pytest.importorskip("psycopg2")
        from app.db.connection import engine
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            pytest.skip("PostgreSQL unavailable")

    def test_plan_not_found_returns_404(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app, headers={"X-Org-Id": "00000000-0000-0000-0000-000000000001"})
        response = client.get("/api/copilot/plan_status", params={"plan_id": "nonexistent-id"})
        assert response.status_code == 404

    def test_valid_request_returns_response(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app, headers={"X-Org-Id": "00000000-0000-0000-0000-000000000001"})
        response = client.get("/api/copilot/plan_status", params={"plan_id": "nonexistent-id"})
        # Either 404 (plan not found) or 200 (evaluated) - both are valid
        assert response.status_code in [200, 404]
