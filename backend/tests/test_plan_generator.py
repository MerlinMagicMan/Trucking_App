"""
Tests for Plan Generator - the decision core of Phase 0
Verifies determinism, multi-load chaining, and plan diversity

CRITICAL: Determinism is non-negotiable. Same input MUST produce same output.
"""
import pytest
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.engine.plan_generator import PlanGenerator
from app.engine.optimizer import OptimizationEngine
from app.engine.economics import EconomicsEngine
from app.models.canonical import (
    TruckSnapshot, HOSSnapshot, CanonicalLoad,
    PickupDeliveryLocation
)
from app.models.plan import Plan


# ============================================================================
# MOCK CONNECTOR FOR TESTING
# ============================================================================

class MockConnector:
    """Mock connector that returns deterministic test loads"""

    def __init__(self):
        self.name = "MockConnector"
        self.test_loads = self._create_test_loads()

    def _create_test_loads(self):
        """Create a set of deterministic test loads"""
        now = datetime.now(timezone.utc)

        loads = [
            # Load 1: Oklahoma City → Dallas (205 miles)
            CanonicalLoad(
                id="test_load_001",
                source="test",
                external_id="TL001",
                posted_at=now,
                equipment="reefer",
                pickup=PickupDeliveryLocation(
                    city="Oklahoma City",
                    state="OK",
                    lat=35.4676,
                    lng=-97.5164,
                    window_start=now + timedelta(hours=2),
                    window_end=now + timedelta(hours=6)
                ),
                delivery=PickupDeliveryLocation(
                    city="Dallas",
                    state="TX",
                    lat=32.7767,
                    lng=-96.7970,
                    window_start=now + timedelta(hours=8),
                    window_end=now + timedelta(hours=12)
                ),
                rate_total=1200.00,
                miles=205.0
            ),

            # Load 2: Dallas → Houston (240 miles)
            CanonicalLoad(
                id="test_load_002",
                source="test",
                external_id="TL002",
                posted_at=now,
                equipment="reefer",
                pickup=PickupDeliveryLocation(
                    city="Dallas",
                    state="TX",
                    lat=32.7767,
                    lng=-96.7970,
                    window_start=now + timedelta(hours=16),
                    window_end=now + timedelta(hours=20)
                ),
                delivery=PickupDeliveryLocation(
                    city="Houston",
                    state="TX",
                    lat=29.7604,
                    lng=-95.3698,
                    window_start=now + timedelta(hours=24),
                    window_end=now + timedelta(hours=28)
                ),
                rate_total=1400.00,
                miles=240.0
            ),

            # Load 3: Dallas → San Antonio (275 miles)
            CanonicalLoad(
                id="test_load_003",
                source="test",
                external_id="TL003",
                posted_at=now,
                equipment="reefer",
                pickup=PickupDeliveryLocation(
                    city="Dallas",
                    state="TX",
                    lat=32.7767,
                    lng=-96.7970,
                    window_start=now + timedelta(hours=18),
                    window_end=now + timedelta(hours=22)
                ),
                delivery=PickupDeliveryLocation(
                    city="San Antonio",
                    state="TX",
                    lat=29.4241,
                    lng=-98.4936,
                    window_start=now + timedelta(hours=26),
                    window_end=now + timedelta(hours=30)
                ),
                rate_total=1600.00,
                miles=275.0
            ),

            # Load 4: Oklahoma City → Kansas City (350 miles) - Different first load option
            CanonicalLoad(
                id="test_load_004",
                source="test",
                external_id="TL004",
                posted_at=now,
                equipment="reefer",
                pickup=PickupDeliveryLocation(
                    city="Oklahoma City",
                    state="OK",
                    lat=35.4676,
                    lng=-97.5164,
                    window_start=now + timedelta(hours=3),
                    window_end=now + timedelta(hours=7)
                ),
                delivery=PickupDeliveryLocation(
                    city="Kansas City",
                    state="KS",
                    lat=39.0997,
                    lng=-94.5786,
                    window_start=now + timedelta(hours=10),
                    window_end=now + timedelta(hours=14)
                ),
                rate_total=1800.00,
                miles=350.0
            ),

            # Load 5: Houston → Laredo (360 miles)
            CanonicalLoad(
                id="test_load_005",
                source="test",
                external_id="TL005",
                posted_at=now,
                equipment="reefer",
                pickup=PickupDeliveryLocation(
                    city="Houston",
                    state="TX",
                    lat=29.7604,
                    lng=-95.3698,
                    window_start=now + timedelta(hours=32),
                    window_end=now + timedelta(hours=36)
                ),
                delivery=PickupDeliveryLocation(
                    city="Laredo",
                    state="TX",
                    lat=27.5306,
                    lng=-99.4803,
                    window_start=now + timedelta(hours=40),
                    window_end=now + timedelta(hours=44)
                ),
                rate_total=1700.00,
                miles=360.0
            ),
        ]

        return loads

    def search_loads(self, lat, lng, radius_miles, equipment="reefer", **kwargs):
        """Return all test loads regardless of position"""
        # Return raw load dicts (even though we're actually returning CanonicalLoads for simplicity)
        return self.test_loads, {"connector": "MockConnector", "count": len(self.test_loads)}

    def fetch_and_normalize(self, truck_lat, truck_lng, radius_miles, **kwargs):
        """Fetch and normalize loads (simplified for testing)"""
        # Return CanonicalLoads directly
        metadata = {"connector": "MockConnector", "count": len(self.test_loads)}
        return self.test_loads, metadata

    def normalize(self, raw_load):
        """Normalize raw load to CanonicalLoad (identity for testing)"""
        return raw_load

    def health_check(self):
        """Health check for connector"""
        return {"status": "healthy", "connector": "MockConnector"}


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_connector():
    """Create mock connector with test loads"""
    return MockConnector()


@pytest.fixture
def optimization_engine(mock_connector):
    """Create optimization engine with mock connector"""
    engine = OptimizationEngine(connectors=[mock_connector])
    return engine


@pytest.fixture
def economics_engine():
    """Create economics engine"""
    return EconomicsEngine()


@pytest.fixture
def plan_generator(optimization_engine, economics_engine):
    """Create plan generator with all dependencies"""
    return PlanGenerator(optimization_engine, economics_engine)


@pytest.fixture
def sample_truck():
    """Create sample truck snapshot in Oklahoma City"""
    return TruckSnapshot(
        current_lat=35.4676,
        current_lng=-97.5164,
        hos=HOSSnapshot(
            drive_remaining_min=660,  # 11 hours
            on_duty_remaining_min=840,  # 14 hours
            cycle_remaining_min=4200  # 70 hours
        )
    )


# ============================================================================
# CRITICAL TESTS
# ============================================================================

def test_plans_are_deterministic(plan_generator, sample_truck):
    """
    CRITICAL: Same input MUST produce identical output
    This is non-negotiable for Phase 0 completion
    """
    # Generate plans twice with same input
    plans1 = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)
    plans2 = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)

    # Must have same number of plans
    assert len(plans1) == len(plans2)

    # Each plan must be identical
    for i in range(len(plans1)):
        plan1 = plans1[i]
        plan2 = plans2[i]

        # Same loads in same order
        assert len(plan1.loads) == len(plan2.loads)
        for j in range(len(plan1.loads)):
            assert plan1.loads[j].load.id == plan2.loads[j].load.id

        # Same financial results
        assert plan1.total_revenue_usd == plan2.total_revenue_usd
        assert plan1.total_costs_usd == plan2.total_costs_usd
        assert plan1.net_profit_usd == plan2.net_profit_usd
        assert plan1.profit_per_day_usd == plan2.profit_per_day_usd

        # Same end location
        assert plan1.end_location_lat == plan2.end_location_lat
        assert plan1.end_location_lng == plan2.end_location_lng

        # Same number of time blocks
        assert len(plan1.time_blocks) == len(plan2.time_blocks)


def test_plans_have_multiple_loads(plan_generator, sample_truck):
    """Verify that generated plans have 2-3 loads (not just 1)"""
    plans = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)

    assert len(plans) > 0, "Should generate at least one plan"

    # At least one plan should have 2+ loads
    multi_load_plans = [p for p in plans if len(p.loads) >= 2]
    assert len(multi_load_plans) > 0, "Should generate at least one multi-load plan"


def test_financial_events_sum_correctly(plan_generator, sample_truck):
    """Verify accounting integrity: all financial events sum to net profit"""
    plans = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)

    for plan in plans:
        # Sum all financial events
        total_from_events = sum(event.amount_usd for event in plan.financial_events)

        # Must equal net profit
        assert abs(total_from_events - plan.net_profit_usd) < 0.01, \
            f"Financial events sum ({total_from_events}) != net profit ({plan.net_profit_usd})"


def test_profit_per_day_calculation(plan_generator, sample_truck):
    """Verify profit_per_day = net_profit / planning_horizon_days"""
    plans = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)

    for plan in plans:
        expected_profit_per_day = plan.net_profit_usd / plan.planning_horizon_days
        assert abs(plan.profit_per_day_usd - expected_profit_per_day) < 0.01, \
            f"profit_per_day ({plan.profit_per_day_usd}) != net_profit/days ({expected_profit_per_day})"


def test_plans_sorted_by_profit_per_day(plan_generator, sample_truck):
    """Verify plans are sorted by profit_per_day descending"""
    plans = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)

    if len(plans) <= 1:
        return  # Nothing to compare

    # Each plan should have profit_per_day >= next plan
    for i in range(len(plans) - 1):
        assert plans[i].profit_per_day_usd >= plans[i+1].profit_per_day_usd, \
            f"Plans not sorted: Plan {i} ({plans[i].profit_per_day_usd}) < Plan {i+1} ({plans[i+1].profit_per_day_usd})"


def test_time_blocks_are_chronological(plan_generator, sample_truck):
    """Verify timeline is chronological with no overlaps or gaps"""
    plans = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)

    for plan in plans:
        time_blocks = plan.time_blocks

        # Check chronological order
        for i in range(len(time_blocks) - 1):
            current = time_blocks[i]
            next_block = time_blocks[i + 1]

            # Current block should end before or at next block start
            assert current.end_time <= next_block.start_time, \
                f"Blocks not chronological: {current.block_type} ends after {next_block.block_type} starts"

            # No gaps (except for final "available" block)
            if next_block.block_type != "available":
                gap_seconds = (next_block.start_time - current.end_time).total_seconds()
                assert gap_seconds < 60, \
                    f"Gap of {gap_seconds} seconds between {current.block_type} and {next_block.block_type}"


# ============================================================================
# ADDITIONAL TESTS
# ============================================================================

def test_generate_plans_returns_list(plan_generator, sample_truck):
    """Basic test: generate_plans returns a list"""
    plans = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)

    assert isinstance(plans, list)
    assert len(plans) <= 3, "Should not return more than max_plans"


def test_each_plan_has_minimum_three_explanations(plan_generator, sample_truck):
    """Verify each plan has at least 3 explanations (Plan model requirement)"""
    plans = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)

    for plan in plans:
        assert len(plan.explanations) >= 3, \
            f"Plan must have at least 3 explanations, got {len(plan.explanations)}"


def test_plan_diversity(plan_generator, sample_truck):
    """Verify plans are strategically different (different first loads or end locations)"""
    plans = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)

    if len(plans) <= 1:
        return  # Can't test diversity with 1 plan

    # Check that not all plans have the same first load
    first_load_ids = [plan.loads[0].load.id for plan in plans]
    unique_first_loads = set(first_load_ids)

    # At least 2 different first loads OR different end locations
    if len(unique_first_loads) == 1:
        # All have same first load - check end locations are different
        from app.engine.hos_checker import calculate_distance

        for i in range(len(plans) - 1):
            distance = calculate_distance(
                plans[i].end_location_lat, plans[i].end_location_lng,
                plans[i+1].end_location_lat, plans[i+1].end_location_lng
            )
            assert distance > 100, \
                "Plans should have different end locations (>100 miles apart) if same first load"
    else:
        # Different first loads - diversity achieved
        assert len(unique_first_loads) >= 2


def test_two_load_plans_for_7_day_horizon(plan_generator, sample_truck):
    """Verify 2-load plans are generated for default 7-day horizon"""
    plans = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)

    # Should have at least one 2-load plan
    two_load_plans = [p for p in plans if len(p.loads) == 2]
    assert len(two_load_plans) > 0, "Should generate at least one 2-load plan for 7-day horizon"


def test_three_load_plans_for_long_horizon(plan_generator, sample_truck):
    """Verify 3-load plans are generated for 10+ day horizons"""
    plans = plan_generator.generate_plans(sample_truck, planning_horizon_days=14, max_plans=3)

    # Should have at least one 3-load plan
    three_load_plans = [p for p in plans if len(p.loads) == 3]
    assert len(three_load_plans) > 0, "Should generate at least one 3-load plan for 14-day horizon"


def test_all_plans_have_valid_plan_ids(plan_generator, sample_truck):
    """Verify each plan has a unique UUID"""
    plans = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)

    plan_ids = [plan.plan_id for plan in plans]

    # All should be UUIDs
    for plan_id in plan_ids:
        assert isinstance(plan_id, UUID)

    # All should be unique
    assert len(set(plan_ids)) == len(plan_ids), "Plan IDs should be unique"


def test_all_plans_have_risk_assessment(plan_generator, sample_truck):
    """Verify risk signals are assessed for all plans"""
    plans = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)

    for plan in plans:
        # Risk signals should be a list (may be empty if no risks)
        assert isinstance(plan.risk_signals, list)


def test_all_plans_have_confidence_level(plan_generator, sample_truck):
    """Verify confidence level is set for all plans"""
    plans = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)

    for plan in plans:
        assert plan.confidence in ["low", "medium", "high"]


def test_all_plans_have_plan_score(plan_generator, sample_truck):
    """Verify plan score is calculated (0-100)"""
    plans = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)

    for plan in plans:
        assert 0 <= plan.plan_score <= 100, \
            f"Plan score must be 0-100, got {plan.plan_score}"


def test_empty_first_loads_returns_empty_plans(plan_generator):
    """Edge case: If no first loads available, return empty list"""
    # Create truck in remote location where mock connector won't find loads
    # (Mock connector returns loads for any position, so we need to test with empty connector)

    empty_engine = OptimizationEngine(connectors=[])
    empty_generator = PlanGenerator(empty_engine, EconomicsEngine())

    truck = TruckSnapshot(
        current_lat=0.0,
        current_lng=0.0,
        hos=HOSSnapshot(drive_remaining_min=660, on_duty_remaining_min=840, cycle_remaining_min=4200)
    )

    plans = empty_generator.generate_plans(truck, planning_horizon_days=7, max_plans=3)

    assert plans == [], "Should return empty list when no first loads available"


def test_loads_analyzed_tracked(plan_generator, sample_truck):
    """Verify loads_analyzed is tracked in plans"""
    plans = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)

    for plan in plans:
        assert plan.loads_analyzed > 0, "Should track number of loads analyzed"


def test_plans_have_complete_financial_breakdown(plan_generator, sample_truck):
    """Verify financial events cover all cost categories"""
    plans = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)

    for plan in plans:
        event_types = [e.event_type for e in plan.financial_events]

        # Should have revenue events
        assert "revenue" in event_types, "Plan should have revenue events"

        # Should have fuel cost
        assert "fuel_cost" in event_types, "Plan should have fuel cost"

        # All costs should be negative
        for event in plan.financial_events:
            if event.event_type in ["fuel_cost", "toll_cost", "waiting_cost", "maintenance_reserve", "opportunity_cost"]:
                assert event.amount_usd < 0, f"{event.event_type} should be negative"

        # All revenues should be positive
        for event in plan.financial_events:
            if event.event_type == "revenue":
                assert event.amount_usd > 0, "Revenue should be positive"


def test_calculation_details_present_in_financial_events(plan_generator, sample_truck):
    """Verify all financial events have calculation_details for audit trail"""
    plans = plan_generator.generate_plans(sample_truck, planning_horizon_days=7, max_plans=3)

    for plan in plans:
        for event in plan.financial_events:
            assert event.calculation_details is not None, \
                f"{event.event_type} missing calculation_details"
            assert isinstance(event.calculation_details, dict)
            assert len(event.calculation_details) > 0, \
                f"{event.event_type} has empty calculation_details"
