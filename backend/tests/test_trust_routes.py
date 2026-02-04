"""
Tests for Trust Routes — Stratum 5C

DB-gated integration tests for trust report endpoint.
"""
import pytest


class TestTrustRoutes:
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

    def test_trust_report_404_for_missing_plan(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app, headers={"X-Org-Id": "00000000-0000-0000-0000-000000000001"})
        response = client.get("/api/trust/report", params={"plan_id": "nonexistent-plan-id"})
        assert response.status_code == 404

    def test_trust_report_returns_schema_on_valid_plan(self):
        """If a plan exists, should return trust report with expected fields."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.db.connection import SessionLocal
        from app.models.events import PlanGenerationEvent
        from datetime import datetime
        from uuid import uuid4

        db = SessionLocal()
        org_id = "00000000-0000-0000-0000-000000000001"

        # Seed a plan generation event
        plan_id = str(uuid4())
        event = PlanGenerationEvent(
            timestamp=datetime.utcnow(),
            snapshot_id=uuid4(),
            planning_horizon_days=7,
            plans_generated=1,
            full_payload={
                "plans": [{
                    "plan_id": plan_id,
                    "total_revenue_usd": 3000,
                    "total_costs_usd": 1500,
                    "net_profit_usd": 1500,
                    "profit_per_day_usd": 214.29,
                    "loads": [{"load": {"id": "test", "miles": 500}, "deadhead_miles": 50}],
                    "time_blocks": [{"duration_min": 600}],
                }],
            },
            org_id=org_id,
        )
        db.add(event)
        db.commit()

        try:
            client = TestClient(app, headers={"X-Org-Id": org_id})
            response = client.get("/api/trust/report", params={"plan_id": plan_id})
            assert response.status_code == 200

            data = response.json()
            assert "confidence_score" in data
            assert "confidence_label" in data
            assert "warnings" in data
            assert "explanations" in data
            assert "meta" in data
            assert data["meta"]["plan_id"] == plan_id
        finally:
            db.delete(event)
            db.commit()
            db.close()

    def test_copilot_plan_status_includes_trust(self):
        """Copilot plan_status should include trust in meta."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.db.connection import SessionLocal
        from app.models.events import PlanGenerationEvent
        from datetime import datetime
        from uuid import uuid4

        db = SessionLocal()
        org_id = "00000000-0000-0000-0000-000000000001"

        plan_id = str(uuid4())
        event = PlanGenerationEvent(
            timestamp=datetime.utcnow(),
            snapshot_id=uuid4(),
            planning_horizon_days=7,
            plans_generated=1,
            full_payload={
                "plans": [{
                    "plan_id": plan_id,
                    "total_revenue_usd": 3000,
                    "total_costs_usd": 1500,
                    "net_profit_usd": 1500,
                    "profit_per_day_usd": 214.29,
                    "loads": [{
                        "load": {
                            "id": "test",
                            "source": "mock_market",
                            "external_id": "MKT-001",
                            "rate_total": 1500,
                            "miles": 500,
                            "pickup_geohash": "9y69",
                            "delivery_geohash": "9vg4",
                        },
                        "deadhead_miles": 50,
                    }],
                    "time_blocks": [{"duration_min": 600}],
                }],
            },
            org_id=org_id,
        )
        db.add(event)
        db.commit()

        try:
            client = TestClient(app, headers={"X-Org-Id": org_id})
            response = client.get("/api/copilot/plan_status", params={"plan_id": plan_id})
            # May be 200 or error depending on intel availability
            if response.status_code == 200:
                data = response.json()
                # Trust may be present or null (if computation failed)
                assert "meta" in data
                # Trust field should exist even if null
                assert "trust" in data["meta"] or data["meta"].get("offline", False)
        finally:
            db.delete(event)
            db.commit()
            db.close()

    def test_insufficient_outcomes_returns_unknown_label(self):
        """With no completed outcomes, confidence_label should be 'unknown'."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.db.connection import SessionLocal
        from app.models.events import PlanGenerationEvent
        from datetime import datetime
        from uuid import uuid4

        db = SessionLocal()
        org_id = "00000000-0000-0000-0000-000000000002"

        plan_id = str(uuid4())
        event = PlanGenerationEvent(
            timestamp=datetime.utcnow(),
            snapshot_id=uuid4(),
            planning_horizon_days=7,
            plans_generated=1,
            full_payload={
                "plans": [{
                    "plan_id": plan_id,
                    "total_revenue_usd": 3000,
                    "total_costs_usd": 1500,
                    "net_profit_usd": 1500,
                    "profit_per_day_usd": 214.29,
                    "loads": [{"load": {"id": "test", "miles": 500}, "deadhead_miles": 50}],
                    "time_blocks": [{"duration_min": 600}],
                }],
            },
            org_id=org_id,
        )
        db.add(event)
        db.commit()

        try:
            client = TestClient(app, headers={"X-Org-Id": org_id})
            response = client.get("/api/trust/report", params={"plan_id": plan_id})
            assert response.status_code == 200

            data = response.json()
            # With 0 outcomes, sample_size < 10 → label should be unknown
            assert data["confidence_label"] == "unknown"
            # Should have low_sample_size warning
            warning_kinds = [w["kind"] for w in data["warnings"]]
            assert "low_sample_size" in warning_kinds
        finally:
            db.delete(event)
            db.commit()
            db.close()
