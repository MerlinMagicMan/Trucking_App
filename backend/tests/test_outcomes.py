"""
Tests for Plan Outcomes — Actuals vs Estimates (Phase 5, Stratum 4A)
"""
import pytest
from decimal import Decimal
from app.api.outcome_routes import _compute_variance_pct
from app.outcomes.snapshotting import _dec, _dec_str, extract_prediction_from_plan as _extract_prediction_from_plan


# ---- Decimal helpers ----

class TestDecimalHelpers:
    def test_dec_none(self):
        assert _dec(None) is None

    def test_dec_float(self):
        result = _dec(1500.456)
        assert result == Decimal("1500.46")

    def test_dec_string(self):
        result = _dec("2500.999")
        assert result == Decimal("2501.00")

    def test_dec_int(self):
        result = _dec(1000)
        assert result == Decimal("1000.00")

    def test_dec_str_none(self):
        assert _dec_str(None) is None

    def test_dec_str_value(self):
        assert _dec_str(1500.456) == "1500.46"


# ---- Variance calculation ----

class TestVarianceCalc:
    def test_exact_match(self):
        result = _compute_variance_pct(Decimal("1000"), Decimal("1000"))
        assert result == Decimal("0.0")

    def test_positive_variance(self):
        result = _compute_variance_pct(Decimal("1000"), Decimal("1200"))
        assert result == Decimal("20.0")

    def test_negative_variance(self):
        result = _compute_variance_pct(Decimal("1000"), Decimal("800"))
        assert result == Decimal("-20.0")

    def test_zero_predicted(self):
        result = _compute_variance_pct(Decimal("0"), Decimal("500"))
        assert result == Decimal("0.00")

    def test_none_predicted(self):
        assert _compute_variance_pct(None, Decimal("500")) is None

    def test_none_actual(self):
        assert _compute_variance_pct(Decimal("1000"), None) is None

    def test_both_none(self):
        assert _compute_variance_pct(None, None) is None

    def test_small_variance_rounds(self):
        result = _compute_variance_pct(Decimal("1000"), Decimal("1033"))
        assert result == Decimal("3.3")

    def test_negative_predicted(self):
        result = _compute_variance_pct(Decimal("-500"), Decimal("-300"))
        assert result == Decimal("40.0")

    def test_large_overrun(self):
        result = _compute_variance_pct(Decimal("1000"), Decimal("1500"))
        assert result == Decimal("50.0")


# ---- Snapshot extraction from plan payload ----

class TestSnapshotExtraction:
    def _make_plan_summary(self):
        """Plan dict as stored in PlanGenerationEvent.full_payload.response.plans[]"""
        return {
            "plan_id": "test-plan-001",
            "num_loads": 3,
            "total_revenue_usd": 4500.0,
            "total_costs_usd": 1200.0,
            "net_profit_usd": 3300.0,
            "profit_per_day_usd": 471.43,
            "end_location": "Dallas, TX",
            "confidence": "high",
            "plan_score": 85.0,
            "load_ids": ["load1", "load2", "load3"],
        }

    def _make_event(self):
        class FakeEvent:
            id = 42
            full_payload = {
                "request": {
                    "planning_horizon_days": 7,
                    "radius_miles": 250,
                }
            }
        return FakeEvent()

    def test_extracts_economics(self):
        plan = self._make_plan_summary()
        event = self._make_event()
        result = _extract_prediction_from_plan(plan, event)
        econ = result["economics_summary"]
        assert econ["gross_revenue"] == "4500.00"
        assert econ["total_costs"] == "1200.00"
        assert econ["net_profit"] == "3300.00"
        assert econ["profit_per_day"] == "471.43"

    def test_extracts_structure(self):
        plan = self._make_plan_summary()
        event = self._make_event()
        result = _extract_prediction_from_plan(plan, event)
        struct = result["structure_summary"]
        assert struct["num_loads"] == 3

    def test_extracts_assumptions(self):
        plan = self._make_plan_summary()
        event = self._make_event()
        result = _extract_prediction_from_plan(plan, event)
        assumptions = result["assumptions"]
        assert assumptions["planning_horizon_days"] == 7
        assert assumptions["radius_miles"] == 250

    def test_summary_plan_no_loads_array(self):
        """Summary plans don't have loads[] with per-load detail."""
        plan = self._make_plan_summary()
        event = self._make_event()
        result = _extract_prediction_from_plan(plan, event)
        # No loads array, so miles come from the loads key (empty list)
        struct = result["structure_summary"]
        assert struct["miles_loaded"] is None or struct["miles_loaded"] == 0

    def test_handles_none_event(self):
        plan = self._make_plan_summary()
        result = _extract_prediction_from_plan(plan, None)
        assert result["assumptions"] == {}


# ---- Integration tests (require DB) ----

class TestOutcomeAPIIntegration:
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

    def test_create_outcome_no_plan(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app, headers={"X-Org-Id": "00000000-0000-0000-0000-000000000001"})
        r = client.post("/api/outcomes", json={"plan_id": "nonexistent-plan-999"})
        # Should succeed (snapshot creation fails gracefully)
        assert r.status_code == 200
        data = r.json()
        assert data["plan_id"] == "nonexistent-plan-999"
        assert data["status"] == "pending"
        assert data["prediction_snapshot_id"] is None

        # Cleanup
        outcome_id = data["id"]
        from app.db.connection import SessionLocal
        from app.models.plan_outcome import PlanOutcome
        db = SessionLocal()
        db.query(PlanOutcome).filter(PlanOutcome.id == outcome_id).delete()
        db.commit()
        db.close()

    def test_duplicate_outcome_returns_409(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app, headers={"X-Org-Id": "00000000-0000-0000-0000-000000000001"})
        r1 = client.post("/api/outcomes", json={"plan_id": "dup-test-plan-v2"})
        assert r1.status_code == 200
        outcome_id = r1.json()["id"]

        r2 = client.post("/api/outcomes", json={"plan_id": "dup-test-plan-v2"})
        assert r2.status_code == 409

        # Cleanup
        from app.db.connection import SessionLocal
        from app.models.plan_outcome import PlanOutcome
        db = SessionLocal()
        db.query(PlanOutcome).filter(PlanOutcome.id == outcome_id).delete()
        db.commit()
        db.close()

    def test_update_outcome_with_actuals(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app, headers={"X-Org-Id": "00000000-0000-0000-0000-000000000001"})
        r = client.post("/api/outcomes", json={"plan_id": "update-test-plan-v2"})
        assert r.status_code == 200
        outcome_id = r.json()["id"]

        r2 = client.patch(f"/api/outcomes/{outcome_id}", json={
            "actual_revenue": "5000.00",
            "actual_fuel_spend": "800.00",
        })
        assert r2.status_code == 200
        data = r2.json()
        assert data["status"] == "complete"
        assert data["actual_revenue"] == "5000.00"
        assert data["actual_fuel_spend"] == "800.00"

        # Cleanup
        from app.db.connection import SessionLocal
        from app.models.plan_outcome import PlanOutcome
        db = SessionLocal()
        db.query(PlanOutcome).filter(PlanOutcome.id == outcome_id).delete()
        db.commit()
        db.close()

    def test_report_no_snapshot_returns_404(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app, headers={"X-Org-Id": "00000000-0000-0000-0000-000000000001"})
        r = client.get("/api/outcomes/report", params={"plan_id": "no-such-plan"})
        assert r.status_code == 404

    def test_summary_empty(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app, headers={"X-Org-Id": "00000000-0000-0000-0000-000000000099"})
        r = client.get("/api/outcomes/summary")
        assert r.status_code == 200
        assert r.json() == []

    def test_prediction_snapshot_no_plan_returns_404(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app, headers={"X-Org-Id": "00000000-0000-0000-0000-000000000001"})
        r = client.post("/api/outcomes/prediction_snapshot", json={"plan_id": "no-such-plan"})
        assert r.status_code == 404
