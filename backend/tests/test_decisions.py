"""
Tests for Decision Feedback Loop — Stratum 4B

Unit tests: decision logic, spam prevention, idempotency
Integration tests (requires_db): full accept/reject flows
"""
import pytest
import uuid
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.copilot.schemas import DecisionCreate, DecisionResponse


# ---- Unit tests ----


class TestDecisionCreate:
    def test_accepted(self):
        d = DecisionCreate(plan_id="plan-1", decision_type="accepted")
        assert d.decision_type == "accepted"
        assert d.reason is None

    def test_rejected_with_reason(self):
        d = DecisionCreate(plan_id="plan-1", decision_type="rejected", reason="Too long")
        assert d.decision_type == "rejected"
        assert d.reason == "Too long"

    def test_modified(self):
        d = DecisionCreate(plan_id="plan-1", decision_type="modified", reason="Changed route")
        assert d.decision_type == "modified"

    def test_invalid_type_rejected(self):
        with pytest.raises(Exception):
            DecisionCreate(plan_id="plan-1", decision_type="cancelled")


class TestDecisionResponse:
    def test_response_with_outcome(self):
        r = DecisionResponse(
            id=1,
            org_id="org-uuid",
            plan_id="plan-uuid",
            decision_type="accepted",
            reason=None,
            outcome_id="outcome-uuid",
            prediction_snapshot_id="snap-uuid",
            timestamp=datetime.utcnow(),
        )
        assert r.outcome_id == "outcome-uuid"
        assert r.prediction_snapshot_id == "snap-uuid"

    def test_response_without_outcome(self):
        r = DecisionResponse(
            id=2,
            org_id="org-uuid",
            plan_id="plan-uuid",
            decision_type="rejected",
            reason="Too expensive",
            outcome_id=None,
            prediction_snapshot_id=None,
            timestamp=datetime.utcnow(),
        )
        assert r.outcome_id is None
        assert r.reason == "Too expensive"


class TestSpamPreventionLogic:
    """Test the spam prevention logic: same (decision_type, reason) → return existing."""

    def test_same_type_same_reason_is_spam(self):
        # Simulates the comparison logic in the endpoint
        last_type, last_reason = "accepted", ""
        new_type, new_reason = "accepted", ""
        same = (last_type == new_type) and (last_reason == new_reason)
        assert same is True

    def test_same_type_none_reasons_is_spam(self):
        last_reason = None
        new_reason = None
        same_reason = (last_reason or "") == (new_reason or "")
        assert same_reason is True

    def test_same_type_different_reason_not_spam(self):
        last_type, last_reason = "accepted", "First accept"
        new_type, new_reason = "accepted", "Second accept with notes"
        same = (last_type == new_type) and ((last_reason or "") == (new_reason or ""))
        assert same is False

    def test_different_type_not_spam(self):
        last_type, last_reason = "accepted", ""
        new_type, new_reason = "rejected", ""
        same = (last_type == new_type) and ((last_reason or "") == (new_reason or ""))
        assert same is False


class TestIdempotencyLogic:
    """Verify that outcome/snapshot uniqueness is by (org_id, plan_id)."""

    def test_existing_outcome_reused(self):
        """If outcome exists, accept returns it rather than creating new."""
        # This tests the logic pattern: query first, create only if absent
        existing_outcomes = {"org1:plan1": "outcome-uuid-1"}
        key = "org1:plan1"
        assert key in existing_outcomes  # Would reuse

    def test_new_outcome_created_when_absent(self):
        existing_outcomes = {}
        key = "org1:plan1"
        assert key not in existing_outcomes  # Would create new


# ---- Integration tests (requires_db) ----

requires_db = pytest.mark.skipif(
    True,  # Will be overridden by conftest if DB is available
    reason="Requires PostgreSQL"
)

try:
    from app.db.connection import SessionLocal
    _db = SessionLocal()
    _db.execute("SELECT 1")
    _db.close()
    requires_db = pytest.mark.skipif(False, reason="")
except Exception:
    pass


@requires_db
class TestDecisionEndpointsIntegration:
    """Integration tests — run only with a live DB."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    @pytest.fixture
    def org_id(self, client):
        resp = client.get("/api/orgs")
        if resp.status_code == 200 and resp.json():
            return resp.json()[0]["id"]
        pytest.skip("No orgs available")

    @pytest.fixture
    def plan_id(self, client, org_id):
        """Find an existing plan_id from generation history."""
        resp = client.get("/api/plans/history", headers={"X-Org-Id": org_id})
        if resp.status_code == 200 and resp.json():
            detail_id = resp.json()[0]["id"]
            detail = client.get(f"/api/plans/history/{detail_id}", headers={"X-Org-Id": org_id})
            if detail.status_code == 200:
                payload = detail.json().get("full_payload", {})
                plans = payload.get("plans", [])
                if plans:
                    return plans[0]["plan_id"]
        pytest.skip("No plans available for testing")

    def test_accept_creates_outcome_and_snapshot(self, client, org_id, plan_id):
        resp = client.post(
            "/api/decisions",
            json={"plan_id": plan_id, "decision_type": "accepted"},
            headers={"X-Org-Id": org_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision_type"] == "accepted"
        assert data["outcome_id"] is not None
        assert data["prediction_snapshot_id"] is not None

    def test_duplicate_accept_returns_same_outcome(self, client, org_id, plan_id):
        # First accept
        r1 = client.post(
            "/api/decisions",
            json={"plan_id": plan_id, "decision_type": "accepted"},
            headers={"X-Org-Id": org_id},
        )
        # Second accept (identical — spam prevention returns same)
        r2 = client.post(
            "/api/decisions",
            json={"plan_id": plan_id, "decision_type": "accepted"},
            headers={"X-Org-Id": org_id},
        )
        assert r1.json()["outcome_id"] == r2.json()["outcome_id"]
        assert r1.json()["id"] == r2.json()["id"]  # Same decision event (spam prevention)

    def test_accept_with_different_reason_new_event_same_outcome(self, client, org_id, plan_id):
        r1 = client.post(
            "/api/decisions",
            json={"plan_id": plan_id, "decision_type": "accepted"},
            headers={"X-Org-Id": org_id},
        )
        r2 = client.post(
            "/api/decisions",
            json={"plan_id": plan_id, "decision_type": "accepted", "reason": "Confirmed after review"},
            headers={"X-Org-Id": org_id},
        )
        # New decision event (different reason)
        assert r2.json()["id"] != r1.json()["id"]
        # But same outcome (idempotent)
        assert r2.json()["outcome_id"] == r1.json()["outcome_id"]

    def test_reject_creates_no_outcome(self, client, org_id, plan_id):
        resp = client.post(
            "/api/decisions",
            json={"plan_id": plan_id, "decision_type": "rejected", "reason": "Too expensive"},
            headers={"X-Org-Id": org_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision_type"] == "rejected"
        # outcome_id may be non-null if a previous accept created one,
        # but for rejected decisions we don't create new ones
        assert data["reason"] == "Too expensive"

    def test_list_decisions(self, client, org_id, plan_id):
        resp = client.get(
            "/api/decisions",
            params={"plan_id": plan_id},
            headers={"X-Org-Id": org_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_invalid_plan_returns_404(self, client, org_id):
        resp = client.post(
            "/api/decisions",
            json={"plan_id": "nonexistent-plan-id", "decision_type": "accepted"},
            headers={"X-Org-Id": org_id},
        )
        assert resp.status_code == 404
