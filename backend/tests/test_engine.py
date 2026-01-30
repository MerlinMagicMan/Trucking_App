"""
Tests for optimization engine rules
Critical requirements:
- HOS-infeasible loads NEVER in top 3
- reload_score always 0-100
- Each recommendation has >=3 explanations
"""
import pytest
from datetime import datetime, timedelta
from app.models.canonical import TruckSnapshot, HOSSnapshot, CanonicalLoad, PickupDeliveryLocation
from app.engine.optimizer import OptimizationEngine
from app.connectors.truckstop import TruckstopConnector


@pytest.fixture
def truck_snapshot():
    """Standard truck snapshot for testing"""
    return TruckSnapshot(
        current_lat=35.4676,  # Oklahoma City
        current_lng=-97.5164,
        hos=HOSSnapshot(
            drive_remaining_min=660,  # 11 hours
            on_duty_remaining_min=840,  # 14 hours
            cycle_remaining_min=4200  # 70 hours
        )
    )


@pytest.fixture
def optimization_engine():
    """Optimization engine with truckstop connector"""
    connector = TruckstopConnector()
    return OptimizationEngine(connectors=[connector])


def test_no_infeasible_loads_in_recommendations(truck_snapshot, optimization_engine):
    """
    CRITICAL: HOS-infeasible loads must NEVER appear in top 3
    """
    result = optimization_engine.optimize(truck_snapshot)

    for rec in result.recommendations:
        assert rec.hos_feasible is True, \
            f"Infeasible load {rec.load_id} found in recommendations"


def test_reload_score_bounds(truck_snapshot, optimization_engine):
    """
    CRITICAL: reload_score must always be between 0 and 100
    """
    result = optimization_engine.optimize(truck_snapshot)

    for rec in result.recommendations:
        assert 0 <= rec.reload_score <= 100, \
            f"Load {rec.load_id} has reload_score {rec.reload_score} outside 0-100 range"


def test_minimum_explanations(truck_snapshot, optimization_engine):
    """
    CRITICAL: Each recommendation must have at least 3 explanations
    """
    result = optimization_engine.optimize(truck_snapshot)

    for rec in result.recommendations:
        assert len(rec.explanations) >= 3, \
            f"Load {rec.load_id} has only {len(rec.explanations)} explanations (need >=3)"


def test_deterministic_results(optimization_engine):
    """
    Same input should produce same output
    """
    snapshot1 = TruckSnapshot(
        current_lat=35.4676,
        current_lng=-97.5164,
        hos=HOSSnapshot(
            drive_remaining_min=660,
            on_duty_remaining_min=840,
            cycle_remaining_min=4200
        )
    )

    snapshot2 = TruckSnapshot(
        current_lat=35.4676,
        current_lng=-97.5164,
        hos=HOSSnapshot(
            drive_remaining_min=660,
            on_duty_remaining_min=840,
            cycle_remaining_min=4200
        )
    )

    result1 = optimization_engine.optimize(snapshot1)
    result2 = optimization_engine.optimize(snapshot2)

    # Same number of recommendations
    assert len(result1.recommendations) == len(result2.recommendations)

    # Same order and load IDs
    for r1, r2 in zip(result1.recommendations, result2.recommendations):
        assert r1.load_id == r2.load_id
        assert r1.rank == r2.rank
        assert r1.reload_score == r2.reload_score


def test_low_hos_returns_warning():
    """
    When HOS is very low, should return warning
    """
    low_hos_snapshot = TruckSnapshot(
        current_lat=35.4676,
        current_lng=-97.5164,
        hos=HOSSnapshot(
            drive_remaining_min=120,  # Only 2 hours
            on_duty_remaining_min=180,
            cycle_remaining_min=300
        )
    )

    connector = TruckstopConnector()
    engine = OptimizationEngine(connectors=[connector])

    result = engine.optimize(low_hos_snapshot)

    # Should have warnings about low HOS
    assert len(result.warnings) > 0
    assert any("Low drive time" in w for w in result.warnings)


def test_fewer_than_three_feasible_loads():
    """
    When <3 feasible loads exist, should return available + warning
    """
    # Truck with very restricted HOS
    tight_hos_snapshot = TruckSnapshot(
        current_lat=35.4676,
        current_lng=-97.5164,
        hos=HOSSnapshot(
            drive_remaining_min=60,  # Only 1 hour - very restrictive
            on_duty_remaining_min=90,
            cycle_remaining_min=120
        )
    )

    connector = TruckstopConnector()
    engine = OptimizationEngine(connectors=[connector])

    result = engine.optimize(tight_hos_snapshot)

    # Should have fewer than 3 recommendations
    assert len(result.recommendations) < 3

    # Should have warning explaining why
    assert len(result.warnings) > 0
    assert result.loads_feasible < 3


def test_ranking_order():
    """
    Recommendations should be ranked 1, 2, 3
    """
    snapshot = TruckSnapshot(
        current_lat=35.4676,
        current_lng=-97.5164,
        hos=HOSSnapshot(
            drive_remaining_min=660,
            on_duty_remaining_min=840,
            cycle_remaining_min=4200
        )
    )

    connector = TruckstopConnector()
    engine = OptimizationEngine(connectors=[connector])

    result = engine.optimize(snapshot)

    if len(result.recommendations) >= 1:
        assert result.recommendations[0].rank == 1

    if len(result.recommendations) >= 2:
        assert result.recommendations[1].rank == 2

    if len(result.recommendations) >= 3:
        assert result.recommendations[2].rank == 3


def test_scores_descending():
    """
    Reload scores should be in descending order (best first)
    """
    snapshot = TruckSnapshot(
        current_lat=35.4676,
        current_lng=-97.5164,
        hos=HOSSnapshot(
            drive_remaining_min=660,
            on_duty_remaining_min=840,
            cycle_remaining_min=4200
        )
    )

    connector = TruckstopConnector()
    engine = OptimizationEngine(connectors=[connector])

    result = engine.optimize(snapshot)

    if len(result.recommendations) >= 2:
        for i in range(len(result.recommendations) - 1):
            assert result.recommendations[i].reload_score >= result.recommendations[i + 1].reload_score, \
                "Recommendations should be sorted by descending reload_score"
