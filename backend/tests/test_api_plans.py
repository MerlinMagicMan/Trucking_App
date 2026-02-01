"""
Tests for Plan Generation API endpoint
Tests POST /api/plans/generate
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.main import app
from app.models.canonical import TruckSnapshot, HOSSnapshot

client = TestClient(app, headers={"X-Org-Id": "00000000-0000-0000-0000-000000000001"})


@pytest.fixture
def sample_truck_payload():
    """Create sample truck snapshot payload for API requests"""
    return {
        "current_lat": 35.4676,
        "current_lng": -97.5164,
        "hos": {
            "drive_remaining_min": 660,
            "on_duty_remaining_min": 840,
            "cycle_remaining_min": 4200
        }
    }


@pytest.mark.requires_db
def test_plans_generate_endpoint_exists(sample_truck_payload):
    """Test that the /api/plans/generate endpoint exists and accepts POST"""
    response = client.post("/api/plans/generate", json=sample_truck_payload)

    # Should not return 404
    assert response.status_code != 404
    # Should return 200 or 422 (validation error), not 405 (method not allowed)
    assert response.status_code in [200, 422]


@pytest.mark.requires_db
def test_plans_generate_returns_valid_response(sample_truck_payload):
    """Test that the endpoint returns a valid GeneratePlansResponse"""
    response = client.post("/api/plans/generate", json=sample_truck_payload)

    assert response.status_code == 200

    data = response.json()

    # Check response structure
    assert "snapshot_id" in data
    assert "plans" in data
    assert "warnings" in data
    assert "metadata" in data

    # Check plans
    assert isinstance(data["plans"], list)
    assert len(data["plans"]) <= 3  # max_plans default is 3

    # If no plans, should have warning
    if len(data["plans"]) == 0:
        assert len(data["warnings"]) > 0


@pytest.mark.requires_db
def test_plans_have_required_fields(sample_truck_payload):
    """Test that each plan has all required fields"""
    response = client.post("/api/plans/generate", json=sample_truck_payload)

    assert response.status_code == 200
    data = response.json()

    if len(data["plans"]) == 0:
        pytest.skip("No plans generated in stub environment")

    for plan in data["plans"]:
        # Identity
        assert "plan_id" in plan
        assert "created_at" in plan

        # Context
        assert "truck_snapshot" in plan
        assert "planning_horizon_days" in plan

        # Loads
        assert "loads" in plan
        assert isinstance(plan["loads"], list)
        assert len(plan["loads"]) >= 1
        assert len(plan["loads"]) <= 3

        # Financial metrics
        assert "total_revenue_usd" in plan
        assert "total_costs_usd" in plan
        assert "net_profit_usd" in plan
        assert "profit_per_day_usd" in plan  # KEY METRIC

        # Timeline
        assert "time_blocks" in plan
        assert len(plan["time_blocks"]) > 0

        # Explanations
        assert "explanations" in plan
        assert len(plan["explanations"]) >= 3

        # Metadata
        assert "plan_score" in plan
        assert "confidence" in plan
        assert "loads_analyzed" in plan


@pytest.mark.requires_db
def test_plans_sorted_by_profit_per_day(sample_truck_payload):
    """Test that plans are sorted by profit_per_day descending"""
    response = client.post("/api/plans/generate", json=sample_truck_payload)

    assert response.status_code == 200
    data = response.json()

    if len(data["plans"]) == 0:
        pytest.skip("No plans generated in stub environment")

    if len(data["plans"]) == 1:
        return  # Nothing to sort

    # Check each plan has profit_per_day >= next plan
    for i in range(len(data["plans"]) - 1):
        assert data["plans"][i]["profit_per_day_usd"] >= data["plans"][i + 1]["profit_per_day_usd"]


@pytest.mark.requires_db
def test_planning_horizon_parameter(sample_truck_payload):
    """Test that planning_horizon_days parameter is respected"""
    response = client.post(
        "/api/plans/generate",
        json=sample_truck_payload,
        params={"planning_horizon_days": 14}
    )

    assert response.status_code == 200
    data = response.json()

    # Check metadata
    assert data["metadata"]["planning_horizon_days"] == 14

    # Check plans reflect the horizon (if any generated)
    for plan in data["plans"]:
        assert plan["planning_horizon_days"] == 14


@pytest.mark.requires_db
def test_max_plans_parameter(sample_truck_payload):
    """Test that max_plans parameter is respected"""
    response = client.post(
        "/api/plans/generate",
        json=sample_truck_payload,
        params={"max_plans": 2}
    )

    assert response.status_code == 200
    data = response.json()

    # Should return at most 2 plans
    assert len(data["plans"]) <= 2


@pytest.mark.requires_db
def test_radius_miles_parameter(sample_truck_payload):
    """Test that radius_miles parameter is accepted"""
    response = client.post(
        "/api/plans/generate",
        json=sample_truck_payload,
        params={"radius_miles": 500}
    )

    assert response.status_code == 200
    data = response.json()

    # Check metadata
    assert data["metadata"]["radius_miles"] == 500


def test_invalid_horizon_too_low(sample_truck_payload):
    """Test that planning_horizon_days < 7 is rejected"""
    response = client.post(
        "/api/plans/generate",
        json=sample_truck_payload,
        params={"planning_horizon_days": 5}
    )

    assert response.status_code == 400
    assert "planning_horizon_days must be between 7 and 14" in response.json()["detail"]


def test_invalid_horizon_too_high(sample_truck_payload):
    """Test that planning_horizon_days > 14 is rejected"""
    response = client.post(
        "/api/plans/generate",
        json=sample_truck_payload,
        params={"planning_horizon_days": 20}
    )

    assert response.status_code == 400
    assert "planning_horizon_days must be between 7 and 14" in response.json()["detail"]


def test_invalid_max_plans_too_low(sample_truck_payload):
    """Test that max_plans < 1 is rejected"""
    response = client.post(
        "/api/plans/generate",
        json=sample_truck_payload,
        params={"max_plans": 0}
    )

    assert response.status_code == 400
    assert "max_plans must be between 1 and 3" in response.json()["detail"]


def test_invalid_max_plans_too_high(sample_truck_payload):
    """Test that max_plans > 3 is rejected"""
    response = client.post(
        "/api/plans/generate",
        json=sample_truck_payload,
        params={"max_plans": 5}
    )

    assert response.status_code == 400
    assert "max_plans must be between 1 and 3" in response.json()["detail"]


@pytest.mark.requires_db
def test_deterministic_plan_generation(sample_truck_payload):
    """Test that same input produces same plans (determinism)"""
    # Generate plans twice with same input
    response1 = client.post("/api/plans/generate", json=sample_truck_payload)
    response2 = client.post("/api/plans/generate", json=sample_truck_payload)

    assert response1.status_code == 200
    assert response2.status_code == 200

    data1 = response1.json()
    data2 = response2.json()

    # Same number of plans
    assert len(data1["plans"]) == len(data2["plans"])

    if len(data1["plans"]) == 0:
        pytest.skip("No plans generated in stub environment")

    # Same plans in same order
    for i in range(len(data1["plans"])):
        plan1 = data1["plans"][i]
        plan2 = data2["plans"][i]

        # Same number of loads
        assert len(plan1["loads"]) == len(plan2["loads"])

        # Same load IDs in same order
        load_ids1 = [load["load"]["id"] for load in plan1["loads"]]
        load_ids2 = [load["load"]["id"] for load in plan2["loads"]]
        assert load_ids1 == load_ids2

        # Same financial results
        assert plan1["profit_per_day_usd"] == plan2["profit_per_day_usd"]
        assert plan1["net_profit_usd"] == plan2["net_profit_usd"]


@pytest.mark.requires_db
def test_all_plans_have_financial_events(sample_truck_payload):
    """Test that all plans have complete financial breakdown"""
    response = client.post("/api/plans/generate", json=sample_truck_payload)

    assert response.status_code == 200
    data = response.json()

    if len(data["plans"]) == 0:
        pytest.skip("No plans generated in stub environment")

    for plan in data["plans"]:
        assert "financial_events" in plan
        assert len(plan["financial_events"]) > 0

        # Should have revenue events
        event_types = [e["event_type"] for e in plan["financial_events"]]
        assert "revenue" in event_types


@pytest.mark.requires_db
def test_all_plans_have_time_blocks(sample_truck_payload):
    """Test that all plans have complete timeline"""
    response = client.post("/api/plans/generate", json=sample_truck_payload)

    assert response.status_code == 200
    data = response.json()

    if len(data["plans"]) == 0:
        pytest.skip("No plans generated in stub environment")

    for plan in data["plans"]:
        assert "time_blocks" in plan
        assert len(plan["time_blocks"]) > 0

        # Check time blocks are chronological
        for i in range(len(plan["time_blocks"]) - 1):
            current_end = plan["time_blocks"][i]["end_time"]
            next_start = plan["time_blocks"][i + 1]["start_time"]
            assert current_end <= next_start


@pytest.mark.requires_db
def test_metadata_includes_key_info(sample_truck_payload):
    """Test that metadata includes key generation info"""
    response = client.post("/api/plans/generate", json=sample_truck_payload)

    assert response.status_code == 200
    data = response.json()

    metadata = data["metadata"]

    assert "planning_horizon_days" in metadata
    assert "radius_miles" in metadata
    assert "plans_requested" in metadata
    assert "plans_generated" in metadata


def test_invalid_hos_bounds(sample_truck_payload):
    """Test that invalid HOS values are rejected"""
    invalid_payload = sample_truck_payload.copy()
    invalid_payload["hos"]["drive_remaining_min"] = 999  # > 660 max

    response = client.post("/api/plans/generate", json=invalid_payload)

    assert response.status_code == 422  # Validation error


def test_invalid_coordinates(sample_truck_payload):
    """Test that invalid coordinates are rejected"""
    invalid_payload = sample_truck_payload.copy()
    invalid_payload["current_lat"] = 95.0  # > 90 max

    response = client.post("/api/plans/generate", json=invalid_payload)

    assert response.status_code == 422  # Validation error
