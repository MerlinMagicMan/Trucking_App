"""
Tests for API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    """GET /api/health should return ok"""
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'


def test_connectors_health_endpoint():
    """GET /api/connectors/health should check all connectors"""
    response = client.get("/api/connectors/health")

    assert response.status_code == 200
    data = response.json()
    assert 'overall_status' in data
    assert 'connectors' in data
    assert len(data['connectors']) >= 2  # At least truckstop and dat


def test_optimize_endpoint_returns_recommendations():
    """POST /api/optimize should return recommendations"""
    snapshot = {
        "current_lat": 35.4676,
        "current_lng": -97.5164,
        "hos": {
            "drive_remaining_min": 660,
            "on_duty_remaining_min": 840,
            "cycle_remaining_min": 4200
        }
    }

    response = client.post("/api/optimize", json=snapshot)

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert 'snapshot_id' in data
    assert 'recommendations' in data
    assert 'forward_look' in data
    assert 'warnings' in data
    assert 'loads_analyzed' in data
    assert 'loads_feasible' in data


def test_optimize_deterministic():
    """Same input should produce identical output"""
    snapshot = {
        "current_lat": 35.4676,
        "current_lng": -97.5164,
        "hos": {
            "drive_remaining_min": 660,
            "on_duty_remaining_min": 840,
            "cycle_remaining_min": 4200
        }
    }

    response1 = client.post("/api/optimize", json=snapshot)
    response2 = client.post("/api/optimize", json=snapshot)

    assert response1.status_code == 200
    assert response2.status_code == 200

    data1 = response1.json()
    data2 = response2.json()

    # Same number of recommendations
    assert len(data1['recommendations']) == len(data2['recommendations'])

    # Same load IDs and scores
    for rec1, rec2 in zip(data1['recommendations'], data2['recommendations']):
        assert rec1['load_id'] == rec2['load_id']
        assert rec1['reload_score'] == rec2['reload_score']
        assert rec1['rank'] == rec2['rank']


def test_optimize_validates_hos_bounds():
    """Invalid HOS values should be rejected"""
    snapshot = {
        "current_lat": 35.4676,
        "current_lng": -97.5164,
        "hos": {
            "drive_remaining_min": 999,  # Invalid: exceeds 660 max
            "on_duty_remaining_min": 840,
            "cycle_remaining_min": 4200
        }
    }

    response = client.post("/api/optimize", json=snapshot)

    assert response.status_code == 422  # Validation error


def test_optimize_validates_coordinates():
    """Invalid coordinates should be rejected"""
    snapshot = {
        "current_lat": 999,  # Invalid latitude
        "current_lng": -97.5164,
        "hos": {
            "drive_remaining_min": 660,
            "on_duty_remaining_min": 840,
            "cycle_remaining_min": 4200
        }
    }

    response = client.post("/api/optimize", json=snapshot)

    assert response.status_code == 422  # Validation error


def test_optimize_all_scores_in_range():
    """All reload scores should be 0-100"""
    snapshot = {
        "current_lat": 35.4676,
        "current_lng": -97.5164,
        "hos": {
            "drive_remaining_min": 660,
            "on_duty_remaining_min": 840,
            "cycle_remaining_min": 4200
        }
    }

    response = client.post("/api/optimize", json=snapshot)
    data = response.json()

    for rec in data['recommendations']:
        assert 0 <= rec['reload_score'] <= 100


def test_optimize_all_have_explanations():
    """All recommendations should have >=3 explanations"""
    snapshot = {
        "current_lat": 35.4676,
        "current_lng": -97.5164,
        "hos": {
            "drive_remaining_min": 660,
            "on_duty_remaining_min": 840,
            "cycle_remaining_min": 4200
        }
    }

    response = client.post("/api/optimize", json=snapshot)
    data = response.json()

    for rec in data['recommendations']:
        assert len(rec['explanations']) >= 3


def test_optimize_returns_warnings_when_appropriate():
    """Should return warnings for tight HOS"""
    snapshot = {
        "current_lat": 35.4676,
        "current_lng": -97.5164,
        "hos": {
            "drive_remaining_min": 120,  # Very low
            "on_duty_remaining_min": 180,
            "cycle_remaining_min": 240
        }
    }

    response = client.post("/api/optimize", json=snapshot)
    data = response.json()

    # Should have warnings about low HOS
    assert len(data['warnings']) > 0
